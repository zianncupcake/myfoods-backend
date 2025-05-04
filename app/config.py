import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import logging

load_dotenv()
log = logging.getLogger("uvicorn")

class Settings(BaseSettings):
    database_url: str = os.getenv("DATABASE_URL", "sqlite://./test_local.db")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0") # Added Redis URL

    class Config:
        env_file = '.env'
        extra = 'ignore'

settings = Settings()

TORTOISE_ORM_CONFIG = {
    "connections": {"default": settings.database_url},
    "apps": {
        "models": {
            "models": ["app.models", "aerich.models"],
            "default_connection": "default",
        },
    },
}

log.info(f"Database URL loaded (first few chars): {settings.database_url[:15]}...")
log.info(f"Redis URL loaded: {settings.redis_url}")
