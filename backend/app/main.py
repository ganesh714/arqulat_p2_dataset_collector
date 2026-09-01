from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.user import User, RoleEnum
from app.core.security import get_password_hash
from app.routers import auth, admin_users, taxonomy, prompts, batches, entries, reviews, jobs, export, notifications

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Seed initial Admin user on startup if it doesn't exist
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.username == settings.ADMIN_USERNAME)
        )
        admin = result.scalar_one_or_none()
        
        if not admin:
            print(f"Seeding initial admin user: {settings.ADMIN_USERNAME}")
            admin = User(
                username=settings.ADMIN_USERNAME,
                email=None,
                password_hash=get_password_hash(settings.ADMIN_PASSWORD),
                role=RoleEnum.admin,
                display_name="Admin"
            )
            session.add(admin)
            await session.commit()
    yield

app = FastAPI(
    title="ARQULAT P2 Dataset Collector",
    description="API for managing 3D AI dataset pipeline",
    version="1.0.0",
    lifespan=lifespan
)

# Set up CORS — origins configurable via CORS_ORIGINS env var (comma-separated)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(admin_users.router)
app.include_router(taxonomy.router)
app.include_router(prompts.router)
app.include_router(batches.router)
app.include_router(entries.router)
app.include_router(reviews.router)
app.include_router(jobs.router)
app.include_router(export.router)
app.include_router(notifications.router)

@app.get("/")
async def root():
    return {"message": "ARQULAT P2 Dataset Collector API is running."}
