from pydantic import BaseModel, ConfigDict
import uuid
from typing import Optional, List
from datetime import datetime
from app.models.batch import BatchStatus


class BatchCreate(BaseModel):
    """Admin creates a batch with a name, a reviewer, and a list of contributors."""
    name: str
    reviewer_id: uuid.UUID
    contributor_ids: List[uuid.UUID]


class BatchResponse(BaseModel):
    id: uuid.UUID
    name: str
    status: BatchStatus
    created_by: uuid.UUID
    reviewer_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PromptAssignmentCreate(BaseModel):
    """Reviewer assigns prompts to a contributor within their batch."""
    prompt_ids: List[uuid.UUID]
    contributor_id: uuid.UUID
