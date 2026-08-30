"""
Job & Worker endpoints.
All endpoints authenticate via the shared WORKER_TOKEN header,
not JWT/user auth.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, text, and_
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import uuid
import base64

from app.core.database import get_db
from app.core.drive_service import get_drive_service
from app.models.job import Job, JobStatus
from app.models.worker import Worker, WorkerStatus
from app.models.entry import Entry
from app.schemas.job import (
    JobClaimResponse, JobCompleteRequest, JobFailRequest, JobResponse,
    WorkerRegister, WorkerHealthResponse,
)
from app.deps.worker_auth import verify_worker_token

router = APIRouter(tags=["jobs_workers"])

WORKER_OFFLINE_THRESHOLD_SECONDS = 45


# ─── Worker Registration ───────────────────────────────────────────
@router.post(
    "/api/workers/register",
    response_model=WorkerHealthResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_worker(
    worker_in: WorkerRegister,
    db: AsyncSession = Depends(get_db),
    _token: bool = Depends(verify_worker_token),
):
    """Register a new worker machine. Idempotent on name."""
    result = await db.execute(select(Worker).where(Worker.name == worker_in.name))
    worker = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if worker:
        # Re-register: update last_seen and mark online
        worker.last_seen = now
        worker.status = WorkerStatus.online
        if worker_in.metadata_info:
            worker.metadata_info = worker_in.metadata_info
    else:
        worker = Worker(
            name=worker_in.name,
            last_seen=now,
            status=WorkerStatus.online,
            metadata_info=worker_in.metadata_info or {},
        )
        db.add(worker)

    await db.commit()
    await db.refresh(worker)
    return _worker_health(worker)


# ─── Job Claim (FOR UPDATE SKIP LOCKED) ────────────────────────────
@router.post("/api/jobs/claim", response_model=Optional[JobClaimResponse])
async def claim_job(
    worker_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _token: bool = Depends(verify_worker_token),
):
    """
    Atomically claim the oldest pending job.
    Uses FOR UPDATE SKIP LOCKED so concurrent workers never grab the same row.
    Returns null/204 if no jobs are available.
    """
    # Raw SQL for the SELECT ... FOR UPDATE SKIP LOCKED pattern
    # SQLAlchemy 2.0 supports .with_for_update(skip_locked=True)
    stmt = (
        select(Job)
        .where(Job.status == JobStatus.pending)
        .order_by(Job.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )

    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        return None

    now = datetime.now(timezone.utc)
    job.status = JobStatus.running
    job.worker_id = worker_id
    job.attempts = job.attempts + 1
    job.started_at = now

    # Also bump the worker's last_seen
    await db.execute(
        update(Worker)
        .where(Worker.id == worker_id)
        .values(last_seen=now, status=WorkerStatus.online)
    )

    await db.commit()
    await db.refresh(job)

    # Fetch linked entry to include script in response
    entry_res = await db.execute(select(Entry).where(Entry.id == job.entry_id))
    entry = entry_res.scalar_one_or_none()

    return JobClaimResponse(
        id=job.id,
        entry_id=job.entry_id,
        entry_code=entry.code if entry else None,
        script=entry.script if entry else None,
        status=job.status.value,
        attempts=job.attempts,
        started_at=job.started_at,
    )


# ─── Job Complete ───────────────────────────────────────────────────
@router.post("/api/jobs/{job_id}/complete", response_model=JobResponse)
async def complete_job(
    job_id: uuid.UUID,
    body: JobCompleteRequest,
    db: AsyncSession = Depends(get_db),
    _token: bool = Depends(verify_worker_token),
):
    """
    Mark a job as done, upload render/GLB via the (stubbed) drive service,
    and store the returned URLs on the Entry.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.running:
        raise HTTPException(status_code=400, detail="Job is not in running state")

    # Fetch the linked entry
    entry_res = await db.execute(select(Entry).where(Entry.id == job.entry_id))
    entry = entry_res.scalar_one_or_none()

    drive = get_drive_service()

    # Upload render image if provided
    if body.render_file_b64:
        render_bytes = base64.b64decode(body.render_file_b64)
        render_path = f"entries/{entry.id}/{body.render_filename}"
        entry.render_url = await drive.upload(render_bytes, render_path)

    # Upload GLB file if provided
    if body.glb_file_b64:
        glb_bytes = base64.b64decode(body.glb_file_b64)
        glb_path = f"entries/{entry.id}/{body.glb_filename}"
        entry.glb_url = await drive.upload(glb_bytes, glb_path)

    now = datetime.now(timezone.utc)
    job.status = JobStatus.done
    job.completed_at = now

    await db.commit()
    await db.refresh(job)
    return job


# ─── Job Fail ───────────────────────────────────────────────────────
@router.post("/api/jobs/{job_id}/fail", response_model=JobResponse)
async def fail_job(
    job_id: uuid.UUID,
    body: JobFailRequest,
    db: AsyncSession = Depends(get_db),
    _token: bool = Depends(verify_worker_token),
):
    """
    Mark a job as failed.
    Increments attempts and appends to error_log.
    NO auto-retry — failed jobs stay as 'failed' for human review.
    A failed script is more likely a real bug than a transient error.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.running:
        raise HTTPException(status_code=400, detail="Job is not in running state")

    now = datetime.now(timezone.utc)

    # Append to error_log with timestamp
    timestamp = now.isoformat()
    new_log_entry = f"[{timestamp}] Attempt #{job.attempts}: {body.error_message}"
    if job.error_log:
        job.error_log = job.error_log + "\n" + new_log_entry
    else:
        job.error_log = new_log_entry

    job.status = JobStatus.failed
    job.completed_at = now

    await db.commit()
    await db.refresh(job)
    return job


# ─── Worker Heartbeat ──────────────────────────────────────────────
@router.post("/api/workers/{worker_id}/heartbeat")
async def worker_heartbeat(
    worker_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _token: bool = Depends(verify_worker_token),
):
    """Update worker's last_seen timestamp."""
    result = await db.execute(select(Worker).where(Worker.id == worker_id))
    worker = result.scalar_one_or_none()

    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    worker.last_seen = datetime.now(timezone.utc)
    worker.status = WorkerStatus.online
    await db.commit()
    return {"status": "ok"}


# ─── Worker Health (computed online/offline) ────────────────────────
@router.get("/api/workers/health", response_model=List[WorkerHealthResponse])
async def workers_health(
    db: AsyncSession = Depends(get_db),
    _token: bool = Depends(verify_worker_token),
):
    """
    List all workers with computed online/offline status.
    A worker is 'offline' if last_seen > 45 seconds ago.
    """
    result = await db.execute(select(Worker))
    workers = result.scalars().all()
    return [_worker_health(w) for w in workers]


# ─── Helper ─────────────────────────────────────────────────────────
def _worker_health(worker: Worker) -> WorkerHealthResponse:
    """Compute online/offline status at query time."""
    now = datetime.now(timezone.utc)
    if worker.last_seen and (now - worker.last_seen) < timedelta(seconds=WORKER_OFFLINE_THRESHOLD_SECONDS):
        computed_status = "online"
    else:
        computed_status = "offline"

    return WorkerHealthResponse(
        id=worker.id,
        name=worker.name,
        last_seen=worker.last_seen,
        status=computed_status,
    )
