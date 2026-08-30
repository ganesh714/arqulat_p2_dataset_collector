from pydantic import BaseModel
import uuid
from typing import Optional, List
from datetime import datetime

# Category Schemas
class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: uuid.UUID
    subphase_id: uuid.UUID
    created_at: datetime
    model_config = {"from_attributes": True}

# Subphase Schemas
class SubphaseBase(BaseModel):
    name: str
    description: Optional[str] = None

class SubphaseCreate(SubphaseBase):
    pass

class SubphaseResponseFlat(SubphaseBase):
    """Flat response for creation — no nested categories."""
    id: uuid.UUID
    phase_id: uuid.UUID
    created_at: datetime
    model_config = {"from_attributes": True}

class SubphaseResponse(SubphaseBase):
    """Nested response for listing — includes categories."""
    id: uuid.UUID
    phase_id: uuid.UUID
    categories: List[CategoryResponse] = []
    created_at: datetime
    model_config = {"from_attributes": True}

# Phase Schemas
class PhaseBase(BaseModel):
    name: str
    description: Optional[str] = None

class PhaseCreate(PhaseBase):
    pass

class PhaseResponseFlat(PhaseBase):
    """Flat response for creation — no nested subphases."""
    id: uuid.UUID
    created_at: datetime
    model_config = {"from_attributes": True}

class PhaseResponse(PhaseBase):
    """Nested response for listing — includes subphases."""
    id: uuid.UUID
    subphases: List[SubphaseResponse] = []
    created_at: datetime
    model_config = {"from_attributes": True}

