import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import boto3
import logging

load_dotenv()
log = logging.getLogger("uvicorn")

class Settings(BaseSettings):
    database_url: str = os.getenv("DATABASE_URL", "sqlite://./test_local.db")
    redis_url: str = os.getenv("REDISCLOUD_URL", "redis://localhost:6379/0") 

    secret_key: str = os.getenv("SECRET_KEY", "samplesecretkey")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1000"))
    algorithm: str = "HS256" 

    google_ai_api_key: str = os.getenv("GOOGLE_AI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")

    r2_account_id: str = os.getenv("R2_ACCOUNT_ID")
    r2_access_key_id: str = os.getenv("R2_ACCESS_KEY_ID")
    r2_secret_access_key: str = os.getenv("R2_SECRET_ACCESS_KEY")
    r2_bucket_name: str = os.getenv("R2_BUCKET_NAME")
    r2_endpoint_url: str = f"https://{r2_account_id}.r2.cloudflarestorage.com"
    r2_public_url_base: str = os.getenv("R2_PUBLIC_URL_BASE")

    class Config:
        env_file = '.env'
        extra = 'ignore'

settings = Settings()

s3_client = None

try:
    s3_client = boto3.client(
        service_name="s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key, 
        region_name="auto" 
        )
    log.info(f"Cloudflare R2 S3 client initialized for bucket: '{settings.r2_bucket_name}' at endpoint: {settings.r2_endpoint_url}")

except Exception as e:
    log.error(f"Failed to initialize Cloudflare R2 S3 client: {e}")

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
