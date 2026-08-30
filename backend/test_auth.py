import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app, lifespan
from app.core.config import settings

async def main():
    async with lifespan(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # This will trigger the lifespan event
            print("Testing login endpoint...")
            response = await ac.post(
                "/api/auth/login", 
                data={"username": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD}
            )
            print("Status Code:", response.status_code)
            if response.status_code == 200:
                print("Login successful! Token:", response.json().get("access_token")[:20] + "...")
            else:
                print("Login failed:", response.json())

if __name__ == "__main__":
    asyncio.run(main())
