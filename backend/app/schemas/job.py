from pydantic import BaseModel, ConfigDict
import uuid
from typing import Optional, Any
from datetime import datetime

# --- Job Schemas ---

class JobClaimResponse(BaseModel):
    id: uuid.UUID
    entry_id: uuid.UUID
    entry_code: Optional[str] = None
    script: Optional[str] = None
    status: str
    attempts: int
    started_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class JobCompleteRequest(BaseModel):
    render_file_b64: Optional[str] = None   # base64-encoded render image
    glb_file_b64: Optional[str] = None      # base64-encoded GLB file
    render_filename: Optional[str] = "render.png"
    glb_filename: Optional[str] = "model.glb"


class JobFailRequest(BaseModel):
    error_message: str


class JobResponse(BaseModel):
    id: uuid.UUID
    entry_id: uuid.UUID
    status: str
    worker_id: Optional[uuid.UUID] = None
    attempts: int
    error_log: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# --- Worker Schemas ---

class WorkerRegister(BaseModel):
    name: str
    metadata_info: Optional[dict] = None


class WorkerHealthResponse(BaseModel):
    id: uuid.UUID
    name: str
    last_seen: Optional[datetime] = None
    status: str  # "online" or "offline", computed at query time

    model_config = ConfigDict(from_attributes=True)
