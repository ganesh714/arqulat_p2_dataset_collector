"""
Worker-token authentication dependency.
Workers authenticate with a shared WORKER_TOKEN from .env,
not with JWT/user auth.
"""

from fastapi import Header, HTTPException, status
from app.core.config import settings


async def verify_worker_token(
    x_worker_token: str = Header(..., alias="X-Worker-Token")
) -> bool:
    """
    FastAPI dependency that checks the X-Worker-Token header
    against the shared WORKER_TOKEN env var.
    """
    if x_worker_token != settings.WORKER_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid worker token",
        )
    return True
