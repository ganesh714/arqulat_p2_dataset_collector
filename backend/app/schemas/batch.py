from pydantic import BaseModel, ConfigDict
import uuid
from typing import Optional, List
from datetime import datetime
from app.models.batch import BatchStatus

class BatchBase(BaseModel):
    name: str

class BatchCreate(BatchBase):
    pass

class BatchResponse(BatchBase):
    id: uuid.UUID
    status: BatchStatus
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class BatchPromptCreate(BaseModel):
    prompt_id: uuid.UUID

class BatchAssignmentCreate(BaseModel):
    prompt_ids: List[uuid.UUID]
    contributor_id: uuid.UUID
    reviewer_id: uuid.UUID

class BatchAssignmentResponse(BaseModel):
    id: uuid.UUID
    batch_id: uuid.UUID
    prompt_id: uuid.UUID
    contributor_id: uuid.UUID
    reviewer_id: uuid.UUID
    assigned_by: uuid.UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
