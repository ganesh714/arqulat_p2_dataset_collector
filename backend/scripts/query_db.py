import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import settings

async def list_users():
    db_url = settings.DATABASE_URL
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    engine = create_async_engine(db_url)
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT id, email, is_superuser FROM users;"))
        for row in res:
            print(dict(row._mapping))
        
        res = await conn.execute(text("SELECT count(*) FROM workers;"))
        print("Workers:", res.scalar())
        
        res = await conn.execute(text("SELECT count(*) FROM categories;"))
        print("Categories:", res.scalar())
            
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(list_users())
