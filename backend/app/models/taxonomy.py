from sqlalchemy import String, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional
import uuid
from app.models.base import Base, UUIDMixin

from sqlalchemy.sql import func
from sqlalchemy import DateTime

class Phase(Base, UUIDMixin):
    __tablename__ = "phases"

    name: Mapped[str] = mapped_column(String, unique=True)
    description: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

    subphases = relationship("Subphase", back_populates="phase", cascade="all, delete-orphan")


class Subphase(Base, UUIDMixin):
    __tablename__ = "subphases"

    phase_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("phases.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

    phase = relationship("Phase", back_populates="subphases")
    categories = relationship("Category", back_populates="subphase", cascade="all, delete-orphan")


class Category(Base, UUIDMixin):
    __tablename__ = "categories"

    subphase_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subphases.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    prompt_counter: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    subphase = relationship("Subphase", back_populates="categories")
    prompts = relationship("Prompt", back_populates="category")

