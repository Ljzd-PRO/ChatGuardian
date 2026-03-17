import logging
import mimetypes
from io import BytesIO
from typing import Optional

import httpx

try:
    from PIL import Image
except ImportError:
    Image = None

logger = logging.getLogger(__name__)


def compress_image(
    image_bytes: bytes,
    max_width: int = 800,
    max_height: int = 600,
    quality: int = 85,
) -> Optional[bytes]:
    """
    压缩图片，保持宽高比。

    Args:
        image_bytes: 原始图片字节数据。
        max_width: 最大宽度（像素）。
        max_height: 最大高度（像素）。
        quality: JPEG 压缩质量（1-100），默认 85。

    Returns:
        压缩后的图片字节数据，如果压缩失败则返回 None。
    """
    if Image is None:
        logger.warning("⚠️ PIL 库未安装，无法压缩图片")
        return None

    try:
        # 打开图片
        img = Image.open(BytesIO(image_bytes))

        # 如果已经小于限制尺寸，直接返回原始数据
        if img.width <= max_width and img.height <= max_height:
            return image_bytes

        # 计算保持宽高比的新尺寸
        width_ratio = max_width / img.width
        height_ratio = max_height / img.height
        ratio = min(width_ratio, height_ratio)

        new_width = int(img.width * ratio)
        new_height = int(img.height * ratio)

        # 重新采样图片
        img.thumbnail((new_width, new_height), Image.Resampling.LANCZOS)

        # 保存为字节
        output = BytesIO()
        # 转换 RGBA 到 RGB（某些格式需要）
        if img.mode in ("RGBA", "LA", "P"):
            rgb_img = Image.new("RGB", img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = rgb_img

        img.save(output, format="JPEG", quality=quality, optimize=True)
        return output.getvalue()
    except Exception as e:
        logger.warning(f"⚠️ 图片压缩失败 | error={e}")
        return None


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
