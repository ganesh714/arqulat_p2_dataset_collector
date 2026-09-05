"""
Batches router.

Workflow:
  1. Admin creates a batch: name + reviewer + list of contributors
  2. Reviewer sees their batches, assigns prompts to contributors
  3. Contributors see entries, write scripts, submit
  4. Reviewer reviews submitted entries
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List
import uuid

from app.core.database import get_db
from app.models.batch import Batch, BatchMember, BatchAssignment, BatchPrompt
from app.models.entry import Entry, EntryStatus
from app.models.prompt import Prompt
from app.models.user import User
from app.schemas.batch import BatchCreate, BatchResponse, PromptAssignmentCreate, BatchPromptCreate
from app.deps.auth import require_admin, require_lead, get_current_user

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
    Optimized: uses bulk queries instead of per-row lookups.
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
    member_user_ids = [m.user_id for m in members]

    # Bulk fetch all member users
    if member_user_ids:
        users_res = await db.execute(select(User).where(User.id.in_(member_user_ids)))
        users_map = {u.id: u for u in users_res.scalars().all()}
    else:
        users_map = {}

    member_list = []
    for m in members:
        u = users_map.get(m.user_id)
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

    # Bulk fetch all prompts and contributors referenced by assignments
    assign_prompt_ids = list({a.prompt_id for a in assignments})
    assign_contributor_ids = list({a.contributor_id for a in assignments})

    if assign_prompt_ids:
        prompts_res = await db.execute(select(Prompt).where(Prompt.id.in_(assign_prompt_ids)))
        prompts_map = {p.id: p for p in prompts_res.scalars().all()}
    else:
        prompts_map = {}

    if assign_contributor_ids:
        contribs_res = await db.execute(select(User).where(User.id.in_(assign_contributor_ids)))
        contribs_map = {u.id: u for u in contribs_res.scalars().all()}
    else:
        contribs_map = {}

    # Bulk fetch all entries for this batch
    entries_res = await db.execute(
        select(Entry).where(Entry.batch_id == batch_id).order_by(Entry.code.asc())
    )
    all_entries = entries_res.scalars().all()
    # Group entries by (prompt_id, contributor_id)
    entries_by_key = {}
    for e in all_entries:
        key = (e.prompt_id, e.contributor_id)
        entries_by_key.setdefault(key, []).append(e)

    rows = []
    for a in assignments:
        prompt = prompts_map.get(a.prompt_id)
        contributor = contribs_map.get(a.contributor_id)
        key = (a.prompt_id, a.contributor_id)
        entries = entries_by_key.get(key, [])

        if not entries:
            rows.append({
                "assignment_id": str(a.id),
                "prompt_code": prompt.code if prompt else None,
                "prompt_text": prompt.prompt_text if prompt else "?",
                "prompt_id": str(a.prompt_id),
                "contributor_name": contributor.display_name if contributor else "?",
                "contributor_id": str(a.contributor_id),
                "entry_code": None,
                "entry_status": "no_entry",
            })
        else:
            for entry in entries:
                rows.append({
                    "assignment_id": str(a.id),
                    "prompt_code": prompt.code if prompt else None,
                    "prompt_text": prompt.prompt_text if prompt else "?",
                    "prompt_id": str(a.prompt_id),
                    "contributor_name": contributor.display_name if contributor else "?",
                    "contributor_id": str(a.contributor_id),
                    "entry_code": entry.code,
                    "entry_status": entry.status.value,
                })

    # Prompts assigned to this batch
    batch_prompts_res = await db.execute(
        select(Prompt).join(BatchPrompt, Prompt.id == BatchPrompt.prompt_id)
        .where(BatchPrompt.batch_id == batch_id)
    )
    batch_prompts = batch_prompts_res.scalars().all()
    batch_prompts_list = [
        {
            "id": str(p.id),
            "code": p.code,
            "prompt_text": p.prompt_text,
            "tags": p.tags,
        }
        for p in batch_prompts
    ]

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
        "batch_prompts": batch_prompts_list,
        "assignments": rows,
    }


# ── Admin: Add Contributors to Existing Batch ────────────────────────

class AddMembersRequest(BaseModel):
    contributor_ids: List[uuid.UUID]

@router.post("/{batch_id}/members")
async def add_members_to_batch(
    batch_id: uuid.UUID,
    body: AddMembersRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Admin adds new contributors to an existing batch.
    Skips users who are already members.
    """
    batch_res = await db.execute(select(Batch).where(Batch.id == batch_id))
    batch = batch_res.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    added = 0
    skipped = 0
    for cid in body.contributor_ids:
        # Check if already a member
        existing = await db.execute(
            select(BatchMember).where(
                and_(BatchMember.batch_id == batch_id, BatchMember.user_id == cid)
            )
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        # Validate user exists and is a contributor
        u_res = await db.execute(select(User).where(User.id == cid))
        u = u_res.scalar_one_or_none()
        if not u or u.role != "contributor":
            skipped += 1
            continue

        db.add(BatchMember(batch_id=batch_id, user_id=cid))
        added += 1

    await db.commit()
    return {"added": added, "skipped": skipped}


# ── Admin/Lead: Assign Prompts to Batch ──────────────────────────────

@router.post("/{batch_id}/prompts")
async def add_prompts_to_batch(
    batch_id: uuid.UUID,
    assignment_in: BatchPromptCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lead)
):
    """
    Admin or Lead assigns prompts to a batch.
    """
    batch_res = await db.execute(select(Batch).where(Batch.id == batch_id))
    batch = batch_res.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    added = 0
    ignored = 0
    for pid in assignment_in.prompt_ids:
        # Check if already added
        existing = await db.execute(
            select(BatchPrompt).where(
                and_(BatchPrompt.batch_id == batch_id, BatchPrompt.prompt_id == pid)
            )
        )
        if existing.scalar_one_or_none():
            ignored += 1
            continue
            
        db.add(BatchPrompt(batch_id=batch_id, prompt_id=pid))
        added += 1

    await db.commit()
    return {"added": added, "ignored": ignored}


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
        # Validate prompt is in this batch
        bp_res = await db.execute(
            select(BatchPrompt).where(
                and_(BatchPrompt.batch_id == batch_id, BatchPrompt.prompt_id == prompt_id)
            )
        )
        if not bp_res.scalar_one_or_none():
            ignored += 1 # Or raise error, but bulk is better with ignoring invalid ones
            continue

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
