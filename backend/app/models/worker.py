from sqlalchemy import String, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid
import enum
from typing import Optional, Any
from app.models.base import Base, UUIDMixin
from sqlalchemy import DateTime

class WorkerStatus(str, enum.Enum):
    online = "online"
    offline = "offline"

class Worker(Base, UUIDMixin):
    __tablename__ = "workers"

    name: Mapped[str] = mapped_column(String, unique=True)
    last_seen: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))
    status: Mapped[WorkerStatus] = mapped_column(
        Enum(WorkerStatus, name="worker_status_enum", create_type=False),
        default=WorkerStatus.offline
    )
    metadata_info: Mapped[Optional[Any]] = mapped_column(JSONB, default=dict)

    jobs = relationship("Job", back_populates="worker")
