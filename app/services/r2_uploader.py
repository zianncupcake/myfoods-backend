import httpx
import mimetypes
import uuid
import asyncio 
from app.config import s3_client, settings
import logging
log = logging.getLogger("uvicorn")

async def upload_image_from_url_to_r2(image_url: str, desired_object_key_prefix: str = "scraped_images") -> dict:
    if not s3_client:
        log.error("[R2Uploader] S3 client not initialized. Check R2 configuration.")
        raise Exception("R2 S3 client not initialized.")
    if not settings.r2_bucket_name:
        log.error("[R2Uploader] r2_bucket_name not configured.")
        raise Exception("r2_bucket_name not configured.")

    log.info(f"[R2Uploader] Attempting to download image from: {image_url}")
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        try:
            response = await client.get(image_url)
            response.raise_for_status()
            image_data = response.content
            content_type = response.headers.get("content-type", "application/octet-stream")
            log.info(f"[R2Uploader] Image downloaded. Content-Type: {content_type}, Size: {len(image_data)} bytes")
        except httpx.HTTPStatusError as e:
            log.error(f"[R2Uploader] HTTP Error downloading image: {e.response.status_code} from {e.request.url}")
            raise Exception(f"Failed to download image: HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            log.error(f"[R2Uploader] Request Error downloading image from {e.request.url}: {e}")
            raise Exception("Failed to download image: Network/Request error") from e

    file_extension = mimetypes.guess_extension(content_type) or ".jpg"
    object_key = f"{desired_object_key_prefix.strip('/')}/{uuid.uuid4()}{file_extension}"

    log.info(f"[R2Uploader] Attempting to upload to R2 bucket '{settings.r2_bucket_name}' with key '{object_key}'")
    try:
        loop = asyncio.get_event_loop()
        # boto3's s3_client.put_object is synchronous, so run it in an executor
        # to avoid blocking the asyncio event loop if this task is awaited by async code.
        await loop.run_in_executor(
            None,  # Uses the default ThreadPoolExecutor
            lambda: s3_client.put_object(
                Bucket=settings.r2_bucket_name,
                Key=object_key,
                Body=image_data,
                ContentType=content_type
                # For public access, configure your R2 bucket's permissions
                # or use Cloudflare Workers/Pages to serve.
                # ACL='public-read' is not typically used with R2 in the same way as S3.
            )
        )
        log.info(f"[R2Uploader] Successfully uploaded to R2: {object_key}")

        public_url = None
        if settings.r2_public_url_base: 
            public_url = f"{str(settings.r2_public_url_base).rstrip('/')}/{object_key}"
        
        return {
            "r2_object_key": object_key,
            "r2_bucket": settings.r2_bucket_name,
            "public_url": public_url,
            "content_type": content_type
        }
    except Exception as e:
        log.error(f"[R2Uploader] Error uploading to R2 for key {object_key}: {e}", exc_info=True)
        raise Exception("Failed to upload image to R2") from e