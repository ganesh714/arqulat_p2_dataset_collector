from sqlalchemy import String, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional
from app.models.base import Base, UUIDMixin, TimestampMixin
import enum

class RoleEnum(str, enum.Enum):
    contributor = "contributor"
    reviewer = "reviewer"
    lead = "lead"
    admin = "admin"

class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    password_hash: Mapped[str] = mapped_column(String)
    role: Mapped[RoleEnum] = mapped_column(
        Enum(RoleEnum, name="role_enum", create_type=False),
        default=RoleEnum.contributor
    )
    display_name: Mapped[str] = mapped_column(String)
    
    # Relationships
    entries = relationship("Entry", back_populates="contributor")
    reviews = relationship("Review", back_populates="reviewer")
