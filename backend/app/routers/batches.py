from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List
import uuid

from app.core.database import get_db
from app.models.batch import Batch, BatchPrompt, BatchAssignment
from app.models.entry import Entry, EntryStatus
from app.models.prompt import Prompt
from app.schemas.batch import BatchCreate, BatchResponse, BatchPromptCreate, BatchAssignmentCreate, BatchAssignmentResponse
from app.deps.auth import require_lead, get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/batches", tags=["batches"])

@router.post("", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
async def create_batch(
    batch_in: BatchCreate,
    db: AsyncSession = Depends(get_db),
    current_lead: User = Depends(require_lead)
):
    batch = Batch(name=batch_in.name, created_by=current_lead.id)
    db.add(batch)
    await db.commit()
    await db.refresh(batch)
    return batch

@router.get("", response_model=List[BatchResponse])
async def list_batches(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Batch))
    return result.scalars().all()

@router.post("/{batch_id}/prompts", status_code=status.HTTP_201_CREATED)
async def add_prompt_to_batch(
    batch_id: uuid.UUID,
    prompt_in: BatchPromptCreate,
    db: AsyncSession = Depends(get_db),
    current_lead: User = Depends(require_lead)
):
    """Add a prompt to a batch."""
    # Ensure batch exists
    batch_res = await db.execute(select(Batch).where(Batch.id == batch_id))
    if not batch_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Batch not found")
        
    # Ensure prompt exists
    prompt_res = await db.execute(select(Prompt).where(Prompt.id == prompt_in.prompt_id))
    if not prompt_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Prompt not found")
        
    bp = BatchPrompt(batch_id=batch_id, prompt_id=prompt_in.prompt_id)
    db.add(bp)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Prompt already added to this batch")
    return {"status": "ok"}

@router.post("/{batch_id}/assignments")
async def assign_prompts(
    batch_id: uuid.UUID,
    assignment_in: BatchAssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_lead: User = Depends(require_lead)
):
    """Assign a contributor and reviewer to prompts in a batch. Handles reassignments safely."""
    # Enforce no self-review
    if assignment_in.contributor_id == assignment_in.reviewer_id:
        raise HTTPException(status_code=400, detail="A user cannot review their own work")
        
    moved = 0
    ignored = 0
    
    for prompt_id in assignment_in.prompt_ids:
        # Check existing assignments for this prompt in this batch
        existing_assign_res = await db.execute(
            select(BatchAssignment).where(
                and_(
                    BatchAssignment.batch_id == batch_id,
                    BatchAssignment.prompt_id == prompt_id
                )
            )
        )
        existing_assignments = existing_assign_res.scalars().all()
        
        can_move = True
        for old_assign in existing_assignments:
            # Check the entry associated with this assignment
            entry_res = await db.execute(
                select(Entry).where(
                    and_(
                        Entry.batch_id == batch_id,
                        Entry.prompt_id == prompt_id,
                        Entry.contributor_id == old_assign.contributor_id
                    )
                )
            )
            entry = entry_res.scalar_one_or_none()
            if entry and entry.status != EntryStatus.draft:
                can_move = False
                break
                
        if not can_move:
            ignored += 1
            continue
            
        # We can move it. Delete old assignments and their draft entries.
        from sqlalchemy import delete
        if existing_assignments:
            for oa in existing_assignments:
                # Delete draft entry
                await db.execute(
                    delete(Entry).where(
                        and_(
                            Entry.batch_id == batch_id,
                            Entry.prompt_id == prompt_id,
                            Entry.contributor_id == oa.contributor_id,
                            Entry.status == EntryStatus.draft
                        )
                    )
                )
                await db.delete(oa)
                
        # Create new assignment
        new_assign = BatchAssignment(
            batch_id=batch_id,
            prompt_id=prompt_id,
            contributor_id=assignment_in.contributor_id,
            reviewer_id=assignment_in.reviewer_id,
            assigned_by=current_lead.id
        )
        db.add(new_assign)
        
        # Lock prompt row and generate atomic entry code
        prompt_res = await db.execute(
            select(Prompt).where(Prompt.id == prompt_id).with_for_update()
        )
        prompt_obj = prompt_res.scalar_one()
        prompt_obj.entry_counter += 1
        entry_code = f"{prompt_obj.code}_v{prompt_obj.entry_counter}" if prompt_obj.code else None

        # Create new draft entry with code
        new_entry = Entry(
            code=entry_code,
            batch_id=batch_id,
            prompt_id=prompt_id,
            contributor_id=assignment_in.contributor_id,
            status=EntryStatus.draft
        )
        db.add(new_entry)
        moved += 1
        
    await db.commit()
    return {"moved": moved, "ignored": ignored}

