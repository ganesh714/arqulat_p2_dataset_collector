"""
Dataset export endpoint.
Exports all approved entries as JSONL matching the training dataset format:
  {prompt, script, category}
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import json

from app.core.database import get_db
from app.models.entry import Entry, EntryStatus
from app.models.prompt import Prompt
from app.models.taxonomy import Category
from app.deps.auth import require_admin
from app.models.user import User

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/dataset")
async def export_dataset(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """
    Export all approved entries as JSONL.
    Each line: {"prompt": "...", "script": "...", "category": "..."}
    Admin-only.
    """
    result = await db.execute(
        select(Entry)
        .where(Entry.status == EntryStatus.approved)
        .options(
            selectinload(Entry.prompt).selectinload(Prompt.category)
        )
    )
    entries = result.scalars().all()

    async def generate_jsonl():
        for entry in entries:
            line = {
                "entry_code": entry.code or "",
                "prompt_code": entry.prompt.code or "",
                "prompt": entry.prompt.prompt_text,
                "script": entry.script or "",
                "category": entry.prompt.category.name if entry.prompt.category else "",
            }
            yield json.dumps(line, ensure_ascii=False) + "\n"

    return StreamingResponse(
        generate_jsonl(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=dataset.jsonl"},
    )
