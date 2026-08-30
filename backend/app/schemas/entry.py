from pydantic import BaseModel, ConfigDict
import uuid
from typing import Optional
from datetime import datetime
from app.models.entry import EntryStatus

class EntryUpdate(BaseModel):
    script: str

class EntryResponse(BaseModel):
    id: uuid.UUID
    code: Optional[str] = None
    prompt_id: uuid.UUID
    batch_id: uuid.UUID
    contributor_id: uuid.UUID
    script: Optional[str] = None
    status: EntryStatus
    render_url: Optional[str] = None
    glb_url: Optional[str] = None
    reviewer_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
