import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

async def clear_recent_prompts():
    async with AsyncSessionLocal() as session:
        # Delete prompts
        await session.execute(text("DELETE FROM prompts;"))
        print("Deleted all prompts.")
        
        # Reset prompt_counter in all categories
        await session.execute(text("UPDATE categories SET prompt_counter = 0;"))
        print("Reset prompt_counter for all categories to 0.")
            
        await session.commit()
        print("Done.")

if __name__ == "__main__":
    asyncio.run(clear_recent_prompts())
