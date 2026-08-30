from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.user import User, RoleEnum
from app.schemas.admin import UserCreate, RoleUpdate
from app.schemas.auth import UserResponse
from app.deps.auth import require_admin, require_lead

router = APIRouter(prefix="/api/users", tags=["admin_users"])

@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin)
):
    """
    Create a new user. Only Admins can create users.
    New users ALWAYS default to 'contributor' role.
    """
    # Check if email exists
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
        
    user = User(
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        display_name=user_in.display_name,
        role=RoleEnum.contributor  # Hard-coded to enforce rule
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

@router.patch("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: uuid.UUID,
    role_update: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin)
):
    """
    Promote or demote a user. Admin only.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if role_update.role == RoleEnum.admin or user.role == RoleEnum.admin:
        raise HTTPException(status_code=400, detail="Cannot assign or modify admin roles via this endpoint")
        
    user.role = role_update.role
    await db.commit()
    await db.refresh(user)
    return user

@router.get("", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lead) # Leads need to see users to assign batches
):
    """
    List all users. Lead+ only.
    """
    result = await db.execute(select(User))
    return result.scalars().all()
