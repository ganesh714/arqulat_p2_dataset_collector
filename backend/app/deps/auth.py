from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User, RoleEnum
from app.schemas.auth import TokenPayload

# We use the standard OAuth2 scheme for swagger UI compatibility
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    
    if token_data.sub is None:
        raise HTTPException(status_code=404, detail="User not found")
        
    result = await db.execute(select(User).where(User.id == token_data.sub))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return user

class RoleChecker:
    def __init__(self, allowed_roles: list[RoleEnum]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: User = Depends(get_current_user)):
        # Admin can do anything
        if user.role == RoleEnum.admin:
            return user
            
        # Role hierarchy
        hierarchy = {
            RoleEnum.admin: 4,
            RoleEnum.lead: 3,
            RoleEnum.reviewer: 2,
            RoleEnum.contributor: 1
        }
        
        user_level = hierarchy.get(user.role, 0)
        
        # Check if user meets the minimum required level from allowed_roles
        # Typically allowed_roles passed will be just one role that indicates the minimum level
        min_required_level = min([hierarchy.get(r, 99) for r in self.allowed_roles])
        
        if user_level < min_required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return user

# Pre-built dependencies
require_admin = RoleChecker([RoleEnum.admin])
require_lead = RoleChecker([RoleEnum.lead])
require_reviewer = RoleChecker([RoleEnum.reviewer])
require_contributor = RoleChecker([RoleEnum.contributor])
