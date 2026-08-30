from sqlalchemy import String, Text, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid
import enum
from typing import Optional, List
from app.models.base import Base, UUIDMixin, TimestampMixin

class EntryStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"
    needs_fix = "needs_fix"

class Entry(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "entries"

    code: Mapped[Optional[str]] = mapped_column(String, unique=True, index=True)
    prompt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("prompts.id"))
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("batches.id"))
    contributor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    script: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[EntryStatus] = mapped_column(
        Enum(EntryStatus, name="entry_status_enum", create_type=False),
        default=EntryStatus.draft
    )
    render_url: Mapped[Optional[str]] = mapped_column(String)
    glb_url: Mapped[Optional[str]] = mapped_column(String)
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text)

    prompt = relationship("Prompt", back_populates="entries")
    batch = relationship("Batch", back_populates="entries")
    contributor = relationship("User", back_populates="entries")
    reviews = relationship("Review", back_populates="entry")
    jobs = relationship("Job", back_populates="entry")
