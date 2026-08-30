from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import uuid

from app.core.database import get_db
from app.models.entry import Entry, EntryStatus
from app.models.review import Review, ReviewAction
from app.models.batch import Batch
from app.models.notification import Notification
from app.schemas.review import ReviewCreate, ReviewResponse
from app.deps.auth import get_current_user, require_reviewer
from app.models.user import User, RoleEnum

router = APIRouter(prefix="/api/reviews", tags=["reviews"])

@router.post("/{entry_id}", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def submit_review(
    entry_id: uuid.UUID,
    review_in: ReviewCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_reviewer) # Reviewer, Lead, or Admin
):
    """
    Submit a review for an entry.
    Updates the entry status accordingly.
    Lead/Admin overrides notify the original reviewer.
    """
    # 1. Fetch the entry
    entry_res = await db.execute(select(Entry).where(Entry.id == entry_id))
    entry = entry_res.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
        
    if entry.status != EntryStatus.submitted:
        raise HTTPException(status_code=400, detail="Only submitted entries can be reviewed")
        
    # 2. Find the assigned reviewer for this entry
    batch_res = await db.execute(select(Batch).where(Batch.id == entry.batch_id))
    batch = batch_res.scalar_one_or_none()
    
    if not batch or not batch.reviewer_id:
        raise HTTPException(status_code=400, detail="No reviewer assigned to this batch")
        
    original_reviewer_id = batch.reviewer_id
    
    # 3. Check permissions and lead override
    is_lead_override = False
    
    if current_user.id != original_reviewer_id:
        if current_user.role in [RoleEnum.lead, RoleEnum.admin]:
            is_lead_override = True
        else:
            raise HTTPException(status_code=403, detail="You are not assigned to review this entry")
            
    # 4. Enforce no-self-review (again, just to be safe if a Lead is overriding their own entry)
    if current_user.id == entry.contributor_id:
        raise HTTPException(status_code=400, detail="A user cannot review their own work")

    # 5. Create Review
    new_review = Review(
        entry_id=entry.id,
        reviewer_id=current_user.id,
        action=review_in.action,
        notes=review_in.notes,
        is_lead_override=is_lead_override
    )
    db.add(new_review)
    
    # 6. Update Entry Status based on action
    if review_in.action == ReviewAction.approved:
        entry.status = EntryStatus.approved
    elif review_in.action == ReviewAction.rejected:
        entry.status = EntryStatus.rejected
    elif review_in.action == ReviewAction.needs_fix:
        entry.status = EntryStatus.needs_fix
        
    # 7. Create notification if lead override
    if is_lead_override:
        notification = Notification(
            recipient_id=original_reviewer_id,
            triggered_by=current_user.id,
            entry_id=entry.id,
            action="lead_override",
            message=f"A Lead has overridden your review for entry {entry.id}. Action taken: {review_in.action.value}."
        )
        db.add(notification)
        
    # 8. Create notification for contributor if rejected or needs_fix
    if review_in.action in [ReviewAction.rejected, ReviewAction.needs_fix]:
        contributor_notification = Notification(
            recipient_id=entry.contributor_id,
            triggered_by=current_user.id,
            entry_id=entry.id,
            action=review_in.action.value,
            message=f"Your entry was reviewed and marked as '{review_in.action.value}'. See notes for details."
        )
        db.add(contributor_notification)
        
    await db.commit()
    await db.refresh(new_review)
    
    return new_review
