import logging
import mimetypes
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


async def download_image_bytes(url: str, timeout: float = 15.0) -> Optional[bytes]:
    """
    Download an image from the given URL and return raw bytes.
    Returns None if the download fails or the content is not an image.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

        content_type = (response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
        if not content_type:
            guessed, _ = mimetypes.guess_type(url)
            content_type = guessed or "image/jpeg"
        if not content_type.startswith("image/"):
            logger.warning(f"⚠️ 跳过非图片资源 | url={url} | content_type={content_type}")
            return None

        return response.content
    except Exception as exc:
        logger.warning(f"⚠️ 下载图片失败，已跳过该图片 | url={url} | error={exc}")
        return None
