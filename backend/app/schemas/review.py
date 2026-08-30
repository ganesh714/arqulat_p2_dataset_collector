from pydantic import BaseModel, ConfigDict
import uuid
from typing import Optional
from datetime import datetime
from app.models.review import ReviewAction

class ReviewCreate(BaseModel):
    action: ReviewAction
    notes: Optional[str] = None

class ReviewResponse(BaseModel):
    id: uuid.UUID
    entry_id: uuid.UUID
    reviewer_id: uuid.UUID
    action: ReviewAction
    notes: Optional[str] = None
    is_lead_override: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
