from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import List, Optional
import uuid
import re
import io

from app.core.database import get_db
from app.models.entry import Entry, EntryStatus
from app.models.batch import Batch
from app.models.job import Job, JobStatus
from app.core.script_assembly import validate_phase2_code, validate_think_block
from app.schemas.entry import EntryUpdate, EntryResponse
from app.schemas.job import JobResponse
from app.deps.auth import get_current_user, require_contributor
from app.models.user import User, RoleEnum

router = APIRouter(prefix="/api/entries", tags=["entries"])


# ─── Helper: check entry access for owning contributor / assigned reviewer / lead / admin ───
async def _get_entry_with_access(
    entry_id: uuid.UUID,
    db: AsyncSession,
    user: User,
) -> Entry:
    """Fetch an entry and verify the user has access to it."""
    entry_res = await db.execute(select(Entry).where(Entry.id == entry_id))
    entry = entry_res.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    # Admin and Lead can see everything
    if user.role in [RoleEnum.admin, RoleEnum.lead]:
        return entry

    # Owning contributor
    if user.role == RoleEnum.contributor and entry.contributor_id == user.id:
        return entry

    # Assigned reviewer
    if user.role == RoleEnum.reviewer:
        batch_res = await db.execute(
            select(Batch).where(
                and_(
                    Batch.id == entry.batch_id,
                    Batch.reviewer_id == user.id,
                )
            )
        )
        if batch_res.scalar_one_or_none():
            return entry

    raise HTTPException(status_code=403, detail="Not authorized to access this entry")


@router.get("", response_model=List[EntryResponse])
async def list_entries(
    batch_id: Optional[uuid.UUID] = None,
    entry_status: Optional[EntryStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List entries based on user role and optional filters.
    Contributors see only their own entries.
    Reviewers see entries assigned to them.
    Lead/Admin see all entries.
    """
    query = select(Entry)
    
    # Base filtering
    if batch_id:
        query = query.where(Entry.batch_id == batch_id)
    if entry_status:
        query = query.where(Entry.status == entry_status)
        
    # Role-based visibility
    if current_user.role == RoleEnum.contributor:
        query = query.where(Entry.contributor_id == current_user.id)
    elif current_user.role == RoleEnum.reviewer:
        # A reviewer sees entries in batches they are assigned to review
        query = query.join(Batch, Entry.batch_id == Batch.id).where(Batch.reviewer_id == current_user.id)
    # Lead and Admin see all, so no additional where clause needed for them

    # Explicit order by 'code' so entries group logically (e.g. diningtable_0001) and don't jump around
    query = query.order_by(Entry.code.asc())

    result = await db.execute(query)
    return result.scalars().all()

@router.patch("/{entry_id}", response_model=EntryResponse)
async def update_entry_script(
    entry_id: uuid.UUID,
    entry_update: EntryUpdate,
    db: AsyncSession = Depends(get_db),
    current_contributor: User = Depends(require_contributor)
):
    """
    Update the script for an entry. Only the assigned contributor can do this.
    Must be in draft, rejected, or needs_fix status.
    """
    entry_res = await db.execute(select(Entry).where(Entry.id == entry_id))
    entry = entry_res.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
        
    if entry.contributor_id != current_contributor.id and current_contributor.role not in [RoleEnum.lead, RoleEnum.admin]:
        raise HTTPException(status_code=403, detail="Not authorized to edit this entry")
        
    if entry.status not in [EntryStatus.draft, EntryStatus.needs_fix]:
        raise HTTPException(status_code=400, detail=f"Cannot edit entry in status: {entry.status}")
        
    entry.think_block = entry_update.think_block
    entry.phase2_code = entry_update.phase2_code
    await db.commit()
    await db.refresh(entry)
    return entry

@router.post("/{entry_id}/submit", response_model=EntryResponse)
async def submit_entry(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_contributor: User = Depends(require_contributor)
):
    """Submit entry for review."""
    entry_res = await db.execute(select(Entry).where(Entry.id == entry_id))
    entry = entry_res.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
        
    if entry.contributor_id != current_contributor.id and current_contributor.role not in [RoleEnum.lead, RoleEnum.admin]:
        raise HTTPException(status_code=403, detail="Not authorized to submit this entry")
        
    if entry.status not in [EntryStatus.draft, EntryStatus.needs_fix]:
        raise HTTPException(status_code=400, detail="Only draft or needs_fix entries can be submitted")
        
    entry.status = EntryStatus.submitted
    
    # Validate before submit
    errors = validate_phase2_code(entry.phase2_code)
    if errors:
        raise HTTPException(status_code=400, detail=" ".join(errors))
        
    # Create a pending job for worker rendering
    new_job = Job(entry_id=entry.id, status=JobStatus.pending, is_test_run=False)
    db.add(new_job)
    
    await db.commit()
    await db.refresh(entry)
    return entry

@router.post("/{entry_id}/withdraw", response_model=EntryResponse)
async def withdraw_entry(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_contributor: User = Depends(require_contributor)
):
    """Withdraw entry from review, back to draft."""
    entry_res = await db.execute(select(Entry).where(Entry.id == entry_id))
    entry = entry_res.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
        
    if entry.contributor_id != current_contributor.id and current_contributor.role not in [RoleEnum.lead, RoleEnum.admin]:
        raise HTTPException(status_code=403, detail="Not authorized to withdraw this entry")
        
    if entry.status != EntryStatus.submitted:
        raise HTTPException(status_code=400, detail="Only submitted entries can be withdrawn")
        
    entry.status = EntryStatus.draft
    await db.commit()
    await db.refresh(entry)
    return entry


@router.post("/{entry_id}/clone", response_model=EntryResponse)
async def clone_entry(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_contributor: User = Depends(require_contributor)
):
    """
    Duplicate an entry into a new 'v2' variation.
    Preserves text fields (think_block, phase2_code) but resets status to draft
    and clears 3D model URLs. Generates a new code (e.g. _v2).
    """
    entry_res = await db.execute(select(Entry).where(Entry.id == entry_id))
    entry = entry_res.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
        
    if entry.contributor_id != current_contributor.id and current_contributor.role not in [RoleEnum.lead, RoleEnum.admin]:
        raise HTTPException(status_code=403, detail="Not authorized to clone this entry")

    # Determine the new code
    base_code = entry.code or str(entry.id)
    # Strip any existing _vX suffix to get the true base code
    base_code = re.sub(r'_v\d+$', '', base_code)
    
    # Find existing vX clones
    like_pattern = f"{base_code}\_v%"
    clones_res = await db.execute(select(Entry).where(Entry.code.like(like_pattern)))
    clones = clones_res.scalars().all()
    
    max_v = 1
    for clone in clones:
        m = re.search(r'_v(\d+)$', clone.code)
        if m:
            v_num = int(m.group(1))
            if v_num > max_v:
                max_v = v_num
                
    new_v = max_v + 1
    new_code = f"{base_code}_v{new_v}"

    new_entry = Entry(
        code=new_code,
        prompt_id=entry.prompt_id,
        batch_id=entry.batch_id,
        contributor_id=entry.contributor_id,
        think_block=entry.think_block,
        phase2_code=entry.phase2_code,
        status=EntryStatus.draft,
    )
    
    db.add(new_entry)
    await db.commit()
    await db.refresh(new_entry)
    return new_entry


# ─── Test Run ───────────────────────────────────────────────────────
@router.post("/{entry_id}/test-run", response_model=JobResponse)
async def test_run_entry(
    entry_id: uuid.UUID,
    entry_update: EntryUpdate,
    db: AsyncSession = Depends(get_db),
    current_contributor: User = Depends(require_contributor),
):
    """
    Create an ephemeral test-run job.
    Does NOT save the script to the entry — only snapshots it on the Job row.
    The worker will use the snapshot. Results go to temp URLs on the Job.
    """
    entry_res = await db.execute(select(Entry).where(Entry.id == entry_id))
    entry = entry_res.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    if entry.contributor_id != current_contributor.id and current_contributor.role not in [RoleEnum.lead, RoleEnum.admin]:
        raise HTTPException(status_code=403, detail="Not authorized")

    if entry.status not in [EntryStatus.draft, EntryStatus.needs_fix]:
        raise HTTPException(status_code=400, detail=f"Cannot test-run entry in status: {entry.status}")

    # Validate
    errors = validate_phase2_code(entry_update.phase2_code)
    if errors:
        raise HTTPException(status_code=400, detail=" ".join(errors))

    # Do NOT save to entry — snapshot onto the Job instead
    new_job = Job(
        entry_id=entry.id,
        status=JobStatus.pending,
        is_test_run=True,
        script_snapshot=entry_update.phase2_code,
        think_block_snapshot=entry_update.think_block,
    )
    db.add(new_job)

    await db.commit()
    await db.refresh(new_job)
    return new_job


# ─── Promote Test Result ────────────────────────────────────────────
from pydantic import BaseModel as _BaseModel

class PromoteTestRequest(_BaseModel):
    job_id: uuid.UUID

@router.post("/{entry_id}/promote-test", response_model=EntryResponse)
async def promote_test_result(
    entry_id: uuid.UUID,
    body: PromoteTestRequest,
    db: AsyncSession = Depends(get_db),
    current_contributor: User = Depends(require_contributor),
):
    """
    Promote a completed test-run result to the permanent entry.
    Copies script snapshot → entry, and temp file URLs → entry.
    """
    entry_res = await db.execute(select(Entry).where(Entry.id == entry_id))
    entry = entry_res.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    if entry.contributor_id != current_contributor.id and current_contributor.role not in [RoleEnum.lead, RoleEnum.admin]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Fetch the job
    job_res = await db.execute(select(Job).where(Job.id == body.job_id))
    job = job_res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.entry_id != entry.id:
        raise HTTPException(status_code=400, detail="Job does not belong to this entry")
    if not job.is_test_run:
        raise HTTPException(status_code=400, detail="Job is not a test run")
    if job.status != JobStatus.done.value and job.status != JobStatus.done:
        raise HTTPException(status_code=400, detail="Job has not completed successfully")

    # Promote script snapshot to entry
    if job.script_snapshot:
        entry.phase2_code = job.script_snapshot
    if job.think_block_snapshot:
        entry.think_block = job.think_block_snapshot

    # Promote temp file URLs to entry
    if job.temp_render_url:
        entry.render_url = job.temp_render_url
    if job.temp_glb_url:
        entry.glb_url = job.temp_glb_url

    await db.commit()
    await db.refresh(entry)
    return entry

# ─── List Jobs for Entry ────────────────────────────────────────────
@router.get("/{entry_id}/jobs", response_model=List[JobResponse])
async def list_entry_jobs(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all jobs for an entry, most recent first."""
    entry = await _get_entry_with_access(entry_id, db, current_user)

    result = await db.execute(
        select(Job)
        .where(Job.entry_id == entry.id)
        .order_by(Job.created_at.desc())
    )
    return result.scalars().all()


# ─── Drive File Streaming (httpx) ────────────────────────────────────
def _extract_drive_file_id(url: str) -> Optional[str]:
    """Extract Google Drive file ID from various URL formats."""
    if not url:
        return None
    m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    return None


def _get_drive_access_token() -> str:
    """Get a valid access token from the Drive service credentials."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        from app.core.drive_service import get_drive_service, GoogleDriveService
        drive = get_drive_service()
        if not isinstance(drive, GoogleDriveService):
            raise HTTPException(status_code=501, detail="Drive service not configured")
        creds = drive.credentials
        logger.info(f"Credentials valid: {creds.valid}, token: {'yes' if creds.token else 'no'}")
        if not creds.valid:
            import google.auth.transport.requests
            creds.refresh(google.auth.transport.requests.Request())
            logger.info(f"After refresh - valid: {creds.valid}, token: {'yes' if creds.token else 'no'}")
        return creds.token
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get drive access token: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get Drive access token: {type(e).__name__}: {e}")


async def _stream_drive_file_httpx(drive_url: str, content_type: str):
    """
    Stream a file from Google Drive via the API using httpx.
    Streams chunks to the client as they arrive — no full buffering.
    """
    import httpx
    import logging
    logger = logging.getLogger(__name__)

    file_id = _extract_drive_file_id(drive_url)
    if not file_id:
        raise HTTPException(status_code=500, detail="Could not parse Drive file ID")

    try:
        access_token = _get_drive_access_token()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token error: {type(e).__name__}: {e}")

    api_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&acknowledgeAbuse=true"
    logger.info(f"Streaming Drive file: {file_id}")

    async def _generate():
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
                async with client.stream(
                    "GET",
                    api_url,
                    headers={"Authorization": f"Bearer {access_token}"},
                ) as resp:
                    logger.info(f"Drive API response: {resp.status_code}")
                    if resp.status_code != 200:
                        body = await resp.aread()
                        logger.error(f"Drive API error: {resp.status_code} - {body[:500]}")
                        return
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        yield chunk
        except Exception as e:
            logger.exception(f"Error streaming from Drive: {e}")

    return StreamingResponse(_generate(), media_type=content_type)


@router.get("/debug/drive-test")
async def debug_drive_test(
    current_user: User = Depends(get_current_user),
):
    """Debug endpoint to test Drive access token retrieval."""
    try:
        token = _get_drive_access_token()
        return {"status": "ok", "token_length": len(token) if token else 0, "token_prefix": token[:10] + "..." if token else None}
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}


@router.get("/{entry_id}/model")
async def get_entry_model(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream the GLB model file from Drive."""
    entry = await _get_entry_with_access(entry_id, db, current_user)
    if not entry.glb_url:
        raise HTTPException(status_code=404, detail="No model available for this entry")
    return await _stream_drive_file_httpx(entry.glb_url, "model/gltf-binary")


@router.get("/{entry_id}/render")
async def get_entry_render(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream the render PNG from Drive."""
    entry = await _get_entry_with_access(entry_id, db, current_user)
    if not entry.render_url:
        raise HTTPException(status_code=404, detail="No render available for this entry")
    return await _stream_drive_file_httpx(entry.render_url, "image/png")


# ─── Temp Test Run File Streaming ───────────────────────────────────

@router.get("/{entry_id}/jobs/{job_id}/temp-model")
async def get_temp_model(
    entry_id: uuid.UUID,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream the temp GLB model from a test-run job."""
    await _get_entry_with_access(entry_id, db, current_user)
    job_res = await db.execute(select(Job).where(Job.id == job_id))
    job = job_res.scalar_one_or_none()
    if not job or not job.temp_glb_url:
        raise HTTPException(status_code=404, detail="Temp model not available")
    return await _stream_drive_file_httpx(job.temp_glb_url, "model/gltf-binary")


@router.get("/{entry_id}/jobs/{job_id}/temp-render")
async def get_temp_render(
    entry_id: uuid.UUID,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream the temp render from a test-run job."""
    await _get_entry_with_access(entry_id, db, current_user)
    job_res = await db.execute(select(Job).where(Job.id == job_id))
    job = job_res.scalar_one_or_none()
    if not job or not job.temp_render_url:
        raise HTTPException(status_code=404, detail="Temp render not available")
    return await _stream_drive_file_httpx(job.temp_render_url, "image/png")

