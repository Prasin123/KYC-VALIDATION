"""Image ingestion for JPG/PNG uploads (citizenship photos/scans, or photographed KYC pages)."""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageOps


class ImageReadError(Exception):
    pass


@dataclass
class LoadedImage:
    image: Image.Image
    pixel_size: tuple[int, int]
    source_format: str


SUPPORTED_FORMATS = {"JPEG", "JPG", "PNG"}


def load_image(file_bytes: bytes) -> LoadedImage:
    try:
        img = Image.open(__import__("io").BytesIO(file_bytes))
        img.load()
    except Exception as e:
        raise ImageReadError(f"Could not read image: {e}") from e

    fmt = (img.format or "UNKNOWN").upper()
    # Respect EXIF orientation (common with phone photos of documents).
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return LoadedImage(image=img, pixel_size=img.size, source_format=fmt)


def rotate(img: Image.Image, degrees: int) -> Image.Image:
    """Rotate clockwise by 90/180/270 (or any angle) without cropping corners."""
    return img.rotate(-degrees, expand=True, fillcolor=(255, 255, 255))
