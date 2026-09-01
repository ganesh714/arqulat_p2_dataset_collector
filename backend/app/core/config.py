from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str = "change_this_in_production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60 * 24 * 7  # 1 week default
    
    # Optional until Drive is implemented
    GOOGLE_DRIVE_FOLDER_ID: Optional[str] = None
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REFRESH_TOKEN: Optional[str] = None
    
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "adminpassword"
    WORKER_TOKEN: str = "worker_secret_token"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
