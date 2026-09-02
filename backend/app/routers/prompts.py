import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from typing import List, Optional
import uuid

from app.core.database import get_db
from app.models.prompt import Prompt
from app.models.taxonomy import Category
from app.schemas.prompt import PromptCreate, PromptResponse, BulkPromptCreate
from app.deps.auth import require_lead, get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/prompts", tags=["prompts"])

# The similarity threshold for rejecting duplicates (0.0 to 1.0)
SIMILARITY_THRESHOLD = 0.8


def _make_code_prefix(category_name: str) -> str:
    """Lowercase, strip spaces and non-alphanumeric chars for the code prefix."""
    return re.sub(r'[^a-z0-9]', '', category_name.lower())


@router.post("", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt(
    prompt_in: PromptCreate,
    db: AsyncSession = Depends(get_db),
    current_lead: User = Depends(require_lead) # Lead or Admin
):
    """
    Create a new prompt. Uses pg_trgm to prevent fuzzy duplicates.
    Generates an atomic human-readable code: {category_name}{seq:04d}
    """
    # 1. Lock the category row to get an atomic counter
    cat_res = await db.execute(
        select(Category).where(Category.id == prompt_in.category_id).with_for_update()
    )
    cat = cat_res.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    # 2. Check for fuzzy duplicates using pg_trgm similarity
    duplicate_query = select(Prompt).where(
        func.similarity(Prompt.prompt_text, prompt_in.prompt_text) > SIMILARITY_THRESHOLD
    )
    dup_res = await db.execute(duplicate_query)
    duplicates = dup_res.scalars().all()
    
    if duplicates and not prompt_in.force_create:
        dup_texts = [d.prompt_text[:50] + "..." for d in duplicates]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Fuzzy duplicate found",
                "similar_prompts": dup_texts,
                "duplicates_found": True
            }
        )

    # 3. Generate atomic code
    cat.prompt_counter += 1
    code_prefix = _make_code_prefix(cat.name)
    code = f"{code_prefix}{cat.prompt_counter:04d}"

    # 4. Insert the new prompt
    new_prompt = Prompt(
        code=code,
        category_id=prompt_in.category_id,
        prompt_text=prompt_in.prompt_text,
        tags=prompt_in.tags,
        created_by=current_lead.id
    )
    db.add(new_prompt)
    await db.commit()
    await db.refresh(new_prompt)
    return new_prompt

@router.post("/bulk", response_model=dict, status_code=status.HTTP_201_CREATED)
async def bulk_create_prompts(
    bulk_in: BulkPromptCreate,
    db: AsyncSession = Depends(get_db),
    current_lead: User = Depends(require_lead)
):
    """
    Bulk create prompts. 
    Returns the number of created prompts and a list of duplicates if any are found (and force_create=False).
    """
    if not bulk_in.prompts:
        return {"created": 0, "duplicates": []}

    # 1. Lock category row
    cat_res = await db.execute(
        select(Category).where(Category.id == bulk_in.category_id).with_for_update()
    )
    cat = cat_res.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    code_prefix = _make_code_prefix(cat.name)
    created_count = 0
    all_duplicates = []

    for text_val in bulk_in.prompts:
        text_val = text_val.strip()
        if not text_val:
            continue

        if not bulk_in.force_create:
            duplicate_query = select(Prompt).where(
                func.similarity(Prompt.prompt_text, text_val) > SIMILARITY_THRESHOLD
            )
            dup_res = await db.execute(duplicate_query)
            duplicates = dup_res.scalars().all()
            if duplicates:
                dup_texts = [d.prompt_text[:50] + "..." for d in duplicates]
                all_duplicates.extend(dup_texts)
                continue

        cat.prompt_counter += 1
        code = f"{code_prefix}{cat.prompt_counter:04d}"

        new_prompt = Prompt(
            code=code,
            category_id=bulk_in.category_id,
            prompt_text=text_val,
            tags=bulk_in.tags,
            created_by=current_lead.id
        )
        db.add(new_prompt)
        created_count += 1

    if all_duplicates and created_count == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Fuzzy duplicates found for all prompts",
                "similar_prompts": all_duplicates,
                "duplicates_found": True
            }
        )
        
    await db.commit()
    
    return {
        "created": created_count,
        "duplicates": all_duplicates
    }

@router.get("", response_model=List[PromptResponse])
async def list_prompts(
    category_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List prompts, optionally filtered by category.
    """
    query = select(Prompt)
    if category_id:
        query = query.where(Prompt.category_id == category_id)
        
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{prompt_id}", response_model=PromptResponse)
async def get_prompt(
    prompt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a single prompt by ID."""
    result = await db.execute(select(Prompt).where(Prompt.id == prompt_id))
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt
