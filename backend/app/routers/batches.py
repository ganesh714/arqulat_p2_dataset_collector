"""
Batches router.

Workflow:
  1. Admin creates a batch: name + reviewer + list of contributors
  2. Reviewer sees their batches, assigns prompts to contributors
  3. Contributors see entries, write scripts, submit
  4. Reviewer reviews submitted entries
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List
import uuid

from app.core.database import get_db
from app.models.batch import Batch, BatchMember, BatchAssignment
from app.models.entry import Entry, EntryStatus
from app.models.prompt import Prompt
from app.models.user import User
from app.schemas.batch import BatchCreate, BatchResponse, PromptAssignmentCreate
from app.deps.auth import require_admin, get_current_user

router = APIRouter(prefix="/api/batches", tags=["batches"])


# ── Admin: Create Batch ──────────────────────────────────────────────

@router.post("", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
async def create_batch(
    batch_in: BatchCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin)
):
    """
    Admin creates a batch with a reviewer and a list of contributors.
    """
    # Validate reviewer exists and is reviewer/lead role
    rev_res = await db.execute(select(User).where(User.id == batch_in.reviewer_id))
    reviewer = rev_res.scalar_one_or_none()
    if not reviewer:
        raise HTTPException(status_code=404, detail="Reviewer user not found")
    if reviewer.role not in ("reviewer", "lead"):
        raise HTTPException(status_code=400, detail=f"User {reviewer.display_name} has role '{reviewer.role}', must be reviewer or lead")

    # Validate contributors exist and have contributor role
    for cid in batch_in.contributor_ids:
        c_res = await db.execute(select(User).where(User.id == cid))
        contributor = c_res.scalar_one_or_none()
        if not contributor:
            raise HTTPException(status_code=404, detail=f"Contributor {cid} not found")
        if contributor.role != "contributor":
            raise HTTPException(status_code=400, detail=f"User {contributor.display_name} has role '{contributor.role}', must be contributor")

    # No self-review: reviewer can't also be a contributor
    if batch_in.reviewer_id in batch_in.contributor_ids:
        raise HTTPException(status_code=400, detail="Reviewer cannot also be a contributor in the same batch")

    batch = Batch(
        name=batch_in.name,
        created_by=current_admin.id,
        reviewer_id=batch_in.reviewer_id,
    )
    db.add(batch)
    await db.flush()  # get batch.id

    # Add contributors as batch members
    for cid in batch_in.contributor_ids:
        db.add(BatchMember(batch_id=batch.id, user_id=cid))

    await db.commit()
    await db.refresh(batch)
    return batch


# ── List Batches ──────────────────────────────────────────────────────

@router.get("", response_model=List[BatchResponse])
async def list_batches(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List batches visible to the current user:
    - Admin: all batches
    - Reviewer: batches where they're the reviewer
    - Contributor: batches where they're a member
    """
    if current_user.role == "admin":
        result = await db.execute(select(Batch))
    elif current_user.role in ("reviewer", "lead"):
        result = await db.execute(select(Batch).where(Batch.reviewer_id == current_user.id))
    else:
        # Contributor: find batches they're a member of
        result = await db.execute(
            select(Batch).join(BatchMember, Batch.id == BatchMember.batch_id)
            .where(BatchMember.user_id == current_user.id)
        )
    return result.scalars().all()


# ── Batch Detail ──────────────────────────────────────────────────────

@router.get("/{batch_id}/detail")
async def get_batch_detail(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns batch info with:
    - reviewer name
    - list of contributors (members)
    - all assignments with resolved names and entry statuses
    """
    batch_res = await db.execute(select(Batch).where(Batch.id == batch_id))
    batch = batch_res.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    # Reviewer
    rev_res = await db.execute(select(User).where(User.id == batch.reviewer_id))
    reviewer = rev_res.scalar_one_or_none()

    # Members (contributors)
    members_res = await db.execute(
        select(BatchMember).where(BatchMember.batch_id == batch_id)
    )
    members = members_res.scalars().all()
    member_list = []
    for m in members:
        u_res = await db.execute(select(User).where(User.id == m.user_id))
        u = u_res.scalar_one_or_none()
        if u:
            member_list.append({
                "id": str(u.id),
                "display_name": u.display_name,
                "email": u.email,
            })

    # Assignments
    assignments_res = await db.execute(
        select(BatchAssignment).where(BatchAssignment.batch_id == batch_id)
    )
    assignments = assignments_res.scalars().all()

    rows = []
    for a in assignments:
        p_res = await db.execute(select(Prompt).where(Prompt.id == a.prompt_id))
        prompt = p_res.scalar_one_or_none()

        c_res = await db.execute(select(User).where(User.id == a.contributor_id))
        contributor = c_res.scalar_one_or_none()

        entry_res = await db.execute(
            select(Entry).where(
                and_(
                    Entry.batch_id == batch_id,
                    Entry.prompt_id == a.prompt_id,
                    Entry.contributor_id == a.contributor_id
                )
            )
        )
        entry = entry_res.scalar_one_or_none()

        rows.append({
            "assignment_id": str(a.id),
            "prompt_code": prompt.code if prompt else None,
            "prompt_text": prompt.prompt_text if prompt else "?",
            "prompt_id": str(a.prompt_id),
            "contributor_name": contributor.display_name if contributor else "?",
            "contributor_id": str(a.contributor_id),
            "entry_code": entry.code if entry else None,
            "entry_status": entry.status.value if entry else "no_entry",
        })

    return {
        "id": str(batch.id),
        "name": batch.name,
        "status": batch.status.value,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "reviewer": {
            "id": str(reviewer.id),
            "display_name": reviewer.display_name,
        } if reviewer else None,
        "contributors": member_list,
        "assignments": rows,
    }


# ── Reviewer: Assign Prompts to Contributors ─────────────────────────

@router.post("/{batch_id}/assignments")
async def assign_prompts(
    batch_id: uuid.UUID,
    assignment_in: PromptAssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Reviewer assigns prompts to a contributor within their batch.
    Only the batch's reviewer (or admin) can do this.
    """
    batch_res = await db.execute(select(Batch).where(Batch.id == batch_id))
    batch = batch_res.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    # Authorization: must be this batch's reviewer OR admin
    if current_user.role != "admin" and batch.reviewer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only this batch's reviewer can assign prompts")

    # Validate contributor is a member of this batch
    member_res = await db.execute(
        select(BatchMember).where(
            and_(BatchMember.batch_id == batch_id, BatchMember.user_id == assignment_in.contributor_id)
        )
    )
    if not member_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="This contributor is not a member of this batch")

    moved = 0
    ignored = 0

    for prompt_id in assignment_in.prompt_ids:
        # Check if already assigned in this batch
        existing_res = await db.execute(
            select(BatchAssignment).where(
                and_(
                    BatchAssignment.batch_id == batch_id,
                    BatchAssignment.prompt_id == prompt_id,
                    BatchAssignment.contributor_id == assignment_in.contributor_id
                )
            )
        )
        if existing_res.scalar_one_or_none():
            ignored += 1
            continue

        # Create assignment
        new_assign = BatchAssignment(
            batch_id=batch_id,
            prompt_id=prompt_id,
            contributor_id=assignment_in.contributor_id,
            assigned_by=current_user.id,
        )
        db.add(new_assign)

        # Lock prompt row and generate atomic entry code
        prompt_res = await db.execute(
            select(Prompt).where(Prompt.id == prompt_id).with_for_update()
        )
        prompt_obj = prompt_res.scalar_one_or_none()
        if not prompt_obj:
            ignored += 1
            continue
        prompt_obj.entry_counter += 1
        entry_code = f"{prompt_obj.code}_v{prompt_obj.entry_counter}" if prompt_obj.code else None

        # Create draft entry
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
