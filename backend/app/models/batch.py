from sqlalchemy import String, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid
import enum
from typing import List
from app.models.base import Base, UUIDMixin, TimestampMixin
from sqlalchemy import UniqueConstraint

class BatchStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    closed = "closed"

class Batch(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "batches"

    name: Mapped[str] = mapped_column(String)
    status: Mapped[BatchStatus] = mapped_column(
        Enum(BatchStatus, name="batch_status_enum", create_type=False),
        default=BatchStatus.open
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))

    batch_prompts = relationship("BatchPrompt", back_populates="batch")
    batch_assignments = relationship("BatchAssignment", back_populates="batch")
    entries = relationship("Entry", back_populates="batch")


class BatchPrompt(Base, UUIDMixin):
    __tablename__ = "batch_prompts"
    __table_args__ = (UniqueConstraint("batch_id", "prompt_id", name="uq_batch_prompt"),)

    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("batches.id"))
    prompt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("prompts.id"))

    batch = relationship("Batch", back_populates="batch_prompts")
    prompt = relationship("Prompt", back_populates="batch_prompts")


class BatchAssignment(Base, UUIDMixin):
    __tablename__ = "batch_assignments"
    __table_args__ = (UniqueConstraint("batch_id", "contributor_id", "prompt_id", name="uq_batch_contributor_prompt"),)

    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("batches.id"))
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    contributor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    prompt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("prompts.id"))
    assigned_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    
    from sqlalchemy.sql import func
    from sqlalchemy import DateTime
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

    batch = relationship("Batch", back_populates="batch_assignments")
