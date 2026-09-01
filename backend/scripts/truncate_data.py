import asyncio
import sys
import os

# Add the parent directory to sys.path so we can import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import settings

async def truncate_tables():
    db_url = settings.DATABASE_URL
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    engine = create_async_engine(db_url)
    
    # Truncate order exactly as requested by user
    tables_to_truncate = [
        "reviews",
        "notifications",
        "jobs",
        "entries",
        "batch_assignments",
        "batch_prompts",
        "batches",
        "prompts"
    ]
    
    print("Connecting to database...")
    async with engine.begin() as conn:
        for table in tables_to_truncate:
            print(f"Truncating {table}...")
            # CASCADE is used to ensure any missed foreign keys are also handled,
            # but we order them carefully anyway.
            await conn.execute(text(f"TRUNCATE TABLE {table} CASCADE;"))
            
        print("Data truncated successfully.")
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(truncate_tables())
