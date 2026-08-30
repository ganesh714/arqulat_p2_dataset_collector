from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import List, Optional
import uuid

from app.core.database import get_db
from app.models.entry import Entry, EntryStatus
from app.models.batch import BatchAssignment
from app.schemas.entry import EntryUpdate, EntryResponse
from app.deps.auth import get_current_user, require_contributor
from app.models.user import User, RoleEnum

router = APIRouter(prefix="/api/entries", tags=["entries"])

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
        # A reviewer sees entries where they are assigned in BatchAssignment
        # We join on BatchAssignment to get entries assigned to them
        query = query.join(
            BatchAssignment, 
            and_(
                Entry.batch_id == BatchAssignment.batch_id,
                Entry.prompt_id == BatchAssignment.prompt_id,
                Entry.contributor_id == BatchAssignment.contributor_id
            )
        ).where(BatchAssignment.reviewer_id == current_user.id)
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
        
    entry.script = entry_update.script
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
    
    # Create a pending job for worker rendering
    from app.models.job import Job, JobStatus
    new_job = Job(entry_id=entry.id, status=JobStatus.pending)
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
