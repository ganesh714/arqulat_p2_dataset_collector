from sqlalchemy import String, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid
import enum
from typing import List, Optional
from app.models.base import Base, UUIDMixin, TimestampMixin
from sqlalchemy import UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy import DateTime

class BatchStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    closed = "closed"


class Batch(Base, UUIDMixin, TimestampMixin):
    """
    A batch is a named work unit created by Admin.
    It has one reviewer and N contributors (via BatchMember).
    The reviewer assigns prompts to contributors within the batch.
    """
    __tablename__ = "batches"

    name: Mapped[str] = mapped_column(String)
    status: Mapped[BatchStatus] = mapped_column(
        Enum(BatchStatus, name="batch_status_enum", create_type=False),
        default=BatchStatus.open
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    reviewer_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)

    members = relationship("BatchMember", back_populates="batch", cascade="all, delete-orphan")
    batch_prompts = relationship("BatchPrompt", back_populates="batch", cascade="all, delete-orphan")
    batch_assignments = relationship("BatchAssignment", back_populates="batch", cascade="all, delete-orphan")
    entries = relationship("Entry", back_populates="batch")


class BatchMember(Base, UUIDMixin):
    """Contributors assigned to a batch by Admin."""
    __tablename__ = "batch_members"
    __table_args__ = (UniqueConstraint("batch_id", "user_id", name="uq_batch_member"),)

    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))

    batch = relationship("Batch", back_populates="members")


class BatchPrompt(Base, UUIDMixin):
    """Prompts assigned to a batch by Admin/Lead."""
    __tablename__ = "batch_prompts"
    __table_args__ = (UniqueConstraint("batch_id", "prompt_id", name="uq_batch_prompt"),)

    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"))
    prompt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("prompts.id"))

    batch = relationship("Batch", back_populates="batch_prompts")
    prompt = relationship("Prompt", back_populates="batch_prompts")


class BatchAssignment(Base, UUIDMixin):
    """
    A prompt assigned to a specific contributor within a batch.
    Created by the batch's reviewer.
    The reviewer is implicit (batch.reviewer_id).
    """
    __tablename__ = "batch_assignments"
    __table_args__ = (UniqueConstraint("batch_id", "contributor_id", "prompt_id", name="uq_batch_contributor_prompt"),)

    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"))
    contributor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    prompt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("prompts.id"))
    assigned_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

    batch = relationship("Batch", back_populates="batch_assignments")
