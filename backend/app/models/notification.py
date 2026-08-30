from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid
from typing import Optional
from app.models.base import Base, UUIDMixin
from sqlalchemy.sql import func
from sqlalchemy import DateTime

class Notification(Base, UUIDMixin):
    __tablename__ = "notifications"

    recipient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    triggered_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("entries.id"))
    action: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text)
    
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True))

    recipient = relationship("User", foreign_keys=[recipient_id])
    triggerer = relationship("User", foreign_keys=[triggered_by])
    entry = relationship("Entry")
