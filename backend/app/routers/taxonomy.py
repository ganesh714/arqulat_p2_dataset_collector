from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
import uuid

from app.core.database import get_db
from app.models.taxonomy import Phase, Subphase, Category
from app.schemas.taxonomy import PhaseCreate, PhaseResponse, PhaseResponseFlat, SubphaseCreate, SubphaseResponse, SubphaseResponseFlat, CategoryCreate, CategoryResponse
from app.deps.auth import require_admin, get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/taxonomy", tags=["taxonomy"])

@router.get("/phases", response_model=List[PhaseResponse])
async def list_taxonomy(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user) # Any logged in user
):
    """
    Get full taxonomy tree (Phases -> Subphases -> Categories).
    """
    result = await db.execute(
        select(Phase).options(
            selectinload(Phase.subphases).selectinload(Subphase.categories)
        )
    )
    return result.scalars().all()

@router.post("/phases", response_model=PhaseResponseFlat, status_code=status.HTTP_201_CREATED)
async def create_phase(
    phase_in: PhaseCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin) # Admin only
):
    phase = Phase(**phase_in.model_dump())
    db.add(phase)
    await db.commit()
    await db.refresh(phase)
    return phase

@router.post("/phases/{phase_id}/subphases", response_model=SubphaseResponseFlat, status_code=status.HTTP_201_CREATED)
async def create_subphase(
    phase_id: uuid.UUID,
    subphase_in: SubphaseCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin)
):
    # Ensure phase exists
    result = await db.execute(select(Phase).where(Phase.id == phase_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Phase not found")
        
    subphase = Subphase(**subphase_in.model_dump(), phase_id=phase_id)
    db.add(subphase)
    await db.commit()
    await db.refresh(subphase)
    return subphase

@router.post("/subphases/{subphase_id}/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    subphase_id: uuid.UUID,
    category_in: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin)
):
    # Ensure subphase exists
    result = await db.execute(select(Subphase).where(Subphase.id == subphase_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Subphase not found")
        
    category = Category(**category_in.model_dump(), subphase_id=subphase_id)
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category

# Note: The database schema itself enforces that Categories cannot have children. 
# There is no API route and no database foreign key to nest beyond Phase -> Subphase -> Category.
