"""Abstract OCR engine interface. Add a new engine by subclassing OCREngine."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np


@dataclass
class OCRWord:
    text: str
    confidence: float | None  # 0-100, or None if the engine can't report one
    box: list[float]  # [x0,y0,x1,y1] in the coordinate space of the image passed in


@dataclass
class OCRResult:
    text: str
    confidence: float | None  # mean word confidence, or None
    words: list[OCRWord] = field(default_factory=list)
    engine: str = ""
    language: str = ""
    error: str | None = None


LANGUAGE_MAP = {
    # app-facing language name -> engine-specific language code(s)
    "english": "eng",
    "nepali": "nep",
    "mixed": "eng+nep",
}


class OCREngine(ABC):
    name: str = "base"

    @abstractmethod
    def recognize(self, image: np.ndarray, language: str = "english") -> OCRResult:
        """Run OCR on a preprocessed image array (grayscale or BGR) and return text + confidence."""
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """Whether this engine's runtime dependency is actually installed/working."""
        raise NotImplementedError
