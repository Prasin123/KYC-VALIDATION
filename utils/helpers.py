"""Small shared helpers used across modules."""
from __future__ import annotations

import uuid
from pathlib import Path


def new_id(prefix: str = "roi") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def clamp_box(box: list[float], width: float, height: float) -> list[float]:
    """Clip an [x0,y0,x1,y1] box to stay inside a width x height canvas."""
    x0, y0, x1, y1 = box
    x0 = max(0, min(x0, width))
    y0 = max(0, min(y0, height))
    x1 = max(0, min(x1, width))
    y1 = max(0, min(y1, height))
    if x1 <= x0:
        x1 = min(width, x0 + 1)
    if y1 <= y0:
        y1 = min(height, y0 + 1)
    return [x0, y0, x1, y1]


def scale_box(box: list[float], from_size: tuple[float, float], to_size: tuple[float, float]) -> list[float]:
    """Rescale a box defined in one canvas size to another (e.g. PDF points -> rendered pixels)."""
    fw, fh = from_size
    tw, th = to_size
    sx, sy = tw / fw, th / fh
    x0, y0, x1, y1 = box
    return [x0 * sx, y0 * sy, x1 * sx, y1 * sy]


def bytes_to_human(n: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"
