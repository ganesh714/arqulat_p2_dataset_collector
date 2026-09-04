from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
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


# ─── Drive File Proxy ───────────────────────────────────────────────
def _extract_drive_file_id(url: str) -> Optional[str]:
    """Extract Google Drive file ID from various URL formats."""
    if not url:
        return None
    # https://drive.google.com/file/d/FILE_ID/view?usp=sharing
    m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    # https://drive.google.com/uc?id=FILE_ID
    m = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    return None


async def _stream_drive_file(entry: Entry, url_field: str, content_type: str):
    """Download file from Drive and return a StreamingResponse."""
    url = getattr(entry, url_field)
    if not url:
        raise HTTPException(status_code=404, detail=f"No {url_field} available for this entry")

    file_id = _extract_drive_file_id(url)
    if not file_id:
        raise HTTPException(status_code=500, detail=f"Could not parse Drive file ID from {url_field}")

    from app.core.drive_service import get_drive_service, GoogleDriveService

    drive = get_drive_service()
    if not isinstance(drive, GoogleDriveService):
        raise HTTPException(status_code=501, detail="Drive service not configured — cannot stream files")

    try:
        request = drive.service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        from googleapiclient.http import MediaIoBaseDownload
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        buffer.seek(0)
        return StreamingResponse(buffer, media_type=content_type)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to download from Drive: {e}")


@router.get("/{entry_id}/model")
async def get_entry_model(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream the GLB model file from Drive."""
    entry = await _get_entry_with_access(entry_id, db, current_user)
    return await _stream_drive_file(entry, "glb_url", "model/gltf-binary")


@router.get("/{entry_id}/render")
async def get_entry_render(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream the render PNG from Drive."""
    entry = await _get_entry_with_access(entry_id, db, current_user)
    return await _stream_drive_file(entry, "render_url", "image/png")


# ─── Temp Test Run File Proxies ─────────────────────────────────────
async def _stream_drive_url(url: str, content_type: str):
    """Download a file from Drive given its URL and return a StreamingResponse."""
    file_id = _extract_drive_file_id(url)
    if not file_id:
        raise HTTPException(status_code=500, detail="Could not parse Drive file ID")

    from app.core.drive_service import get_drive_service, GoogleDriveService
    drive = get_drive_service()
    if not isinstance(drive, GoogleDriveService):
        raise HTTPException(status_code=501, detail="Drive service not configured")

    try:
        request = drive.service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        from googleapiclient.http import MediaIoBaseDownload
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        buffer.seek(0)
        return StreamingResponse(buffer, media_type=content_type)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to download from Drive: {e}")


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
    return await _stream_drive_url(job.temp_glb_url, "model/gltf-binary")


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
    return await _stream_drive_url(job.temp_render_url, "image/png")
