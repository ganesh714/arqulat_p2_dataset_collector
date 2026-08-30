from pydantic import BaseModel, EmailStr
from typing import Optional
from app.models.user import RoleEnum

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    display_name: str
    # role is intentionally omitted here to enforce server-side default of 'contributor'

class RoleUpdate(BaseModel):
    role: RoleEnum
