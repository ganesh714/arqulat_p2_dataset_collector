import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import settings

async def clear_all_except_admin():
    db_url = settings.DATABASE_URL
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    engine = create_async_engine(db_url)
    
    async with engine.begin() as conn:
        # Tables that were truncated last time:
        print("Truncating operational tables...")
        await conn.execute(text("TRUNCATE TABLE reviews CASCADE;"))
        await conn.execute(text("TRUNCATE TABLE notifications CASCADE;"))
        await conn.execute(text("TRUNCATE TABLE jobs CASCADE;"))
        await conn.execute(text("TRUNCATE TABLE entries CASCADE;"))
        await conn.execute(text("TRUNCATE TABLE batch_assignments CASCADE;"))
        await conn.execute(text("TRUNCATE TABLE batch_prompts CASCADE;"))
        await conn.execute(text("TRUNCATE TABLE batches CASCADE;"))
        await conn.execute(text("TRUNCATE TABLE prompts CASCADE;"))
        
        # Now the extra tables: taxonomy and workers
        print("Truncating taxonomy and workers...")
        await conn.execute(text("TRUNCATE TABLE workers CASCADE;"))
        await conn.execute(text("TRUNCATE TABLE categories CASCADE;"))
        await conn.execute(text("TRUNCATE TABLE subphases CASCADE;"))
        await conn.execute(text("TRUNCATE TABLE phases CASCADE;"))
        
        # Finally, delete all non-admin users
        print("Deleting non-admin users...")
        await conn.execute(text("DELETE FROM users WHERE role != 'admin';"))
        
        print("All data removed except admin login.")
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(clear_all_except_admin())
