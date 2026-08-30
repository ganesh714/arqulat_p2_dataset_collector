from sqlalchemy import String, Text, Enum, ForeignKey, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid
import enum
from typing import Optional
from app.models.base import Base, UUIDMixin, TimestampMixin
from sqlalchemy import DateTime

class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"

class Job(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "jobs"

    entry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entries.id"))
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status_enum", create_type=False),
        default=JobStatus.pending
    )
    worker_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("workers.id"))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_log: Mapped[Optional[str]] = mapped_column(Text)
    is_test_run: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    
    started_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))

    entry = relationship("Entry", back_populates="jobs")
    worker = relationship("Worker", back_populates="jobs")
