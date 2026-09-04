import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

async def migrate():
    async with AsyncSessionLocal() as session:
        # Add new columns to jobs table
        migrations = [
            "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS script_snapshot TEXT;",
            "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS think_block_snapshot TEXT;",
            "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS temp_render_url VARCHAR;",
            "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS temp_glb_url VARCHAR;",
        ]
        for sql in migrations:
            print(f"Running: {sql}")
            await session.execute(text(sql))
        
        await session.commit()
        print("Migration complete!")

if __name__ == "__main__":
    asyncio.run(migrate())
