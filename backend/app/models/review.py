from sqlalchemy import String, Text, Enum, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid
import enum
from typing import Optional
from app.models.base import Base, UUIDMixin
from sqlalchemy.sql import func
from sqlalchemy import DateTime

class ReviewAction(str, enum.Enum):
    approved = "approved"
    rejected = "rejected"
    needs_fix = "needs_fix"

class Review(Base, UUIDMixin):
    __tablename__ = "reviews"

    entry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entries.id"))
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    action: Mapped[ReviewAction] = mapped_column(
        Enum(ReviewAction, name="review_action_enum", create_type=False)
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_lead_override: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

    entry = relationship("Entry", back_populates="reviews")
    reviewer = relationship("User", back_populates="reviews")
