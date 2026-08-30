from sqlalchemy import String, Text, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Any, Optional
import uuid
from app.models.base import Base, UUIDMixin, TimestampMixin

class Prompt(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "prompts"

    code: Mapped[Optional[str]] = mapped_column(String, unique=True, index=True)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id"))
    prompt_text: Mapped[str] = mapped_column(Text)
    tags: Mapped[List[Any]] = mapped_column(JSONB, default=list)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    entry_counter: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    category = relationship("Category", back_populates="prompts")
    entries = relationship("Entry", back_populates="prompt")
    batch_prompts = relationship("BatchPrompt", back_populates="prompt")
