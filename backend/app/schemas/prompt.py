from pydantic import BaseModel, ConfigDict
import uuid
from typing import Optional, List, Any
from datetime import datetime

class PromptCreate(BaseModel):
    category_id: uuid.UUID
    prompt_text: str
    tags: List[str] = []
    force_create: bool = False

class BulkPromptCreate(BaseModel):
    category_id: uuid.UUID
    prompts: List[str]
    tags: List[str] = []
    force_create: bool = False

class PromptResponse(BaseModel):
    id: uuid.UUID
    code: Optional[str] = None
    category_id: uuid.UUID
    prompt_text: str
    tags: List[Any] = []
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
