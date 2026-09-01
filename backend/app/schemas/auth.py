from pydantic import BaseModel, EmailStr
import uuid
from typing import Optional
from datetime import datetime
from app.models.user import RoleEnum

class Token(BaseModel):
    access_token: str
    token_type: str
    
class TokenPayload(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: Optional[EmailStr] = None
    role: RoleEnum
    display_name: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
