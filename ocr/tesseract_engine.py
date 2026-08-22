"""Tesseract-based OCR engine. English/Nepali/mixed are supported out of the box
via tesseract-ocr's `eng` and `nep` traineddata; PSM is tunable per field type."""
from __future__ import annotations

import numpy as np
import pytesseract

from ocr.base import OCREngine, OCRResult, OCRWord, LANGUAGE_MAP
from utils.logging import get_logger

log = get_logger(__name__)

# Page segmentation mode per field type -- a single text line vs. a block of
# text needs a different PSM for reliable results.
PSM_BY_FIELD_TYPE = {
    "TEXT": 7, "NAME": 7, "NUMBER": 7, "DATE": 7,
    "ADDRESS": 6, "TABLE": 6, "DEFAULT": 6,
}


class TesseractEngine(OCREngine):
    name = "tesseract"

    def __init__(self):
        self._available: bool | None = None
        self._installed_langs: set[str] | None = None

    def is_available(self) -> bool:
        if self._available is None:
            try:
                pytesseract.get_tesseract_version()
                self._installed_langs = set(pytesseract.get_languages(config=""))
                self._available = True
            except Exception as e:
                log.warning(f"Tesseract not available: {e}")
                self._available = False
                self._installed_langs = set()
        return self._available

    def _resolve_lang(self, language: str) -> str:
        code = LANGUAGE_MAP.get(language, "eng")
        wanted = set(code.split("+"))
        missing = wanted - (self._installed_langs or set())
        if missing:
            log.warning(f"Missing tesseract language pack(s) {missing}; falling back to 'eng'. "
                        f"Install with: apt-get install tesseract-ocr-nep")
            return "eng"
        return code

    def recognize(self, image: np.ndarray, language: str = "english", field_type: str = "DEFAULT") -> OCRResult:
        if not self.is_available():
            return OCRResult(text="", confidence=None, engine=self.name, language=language,
                              error="Tesseract is not installed or not on PATH.")
        lang_code = self._resolve_lang(language)
        psm = PSM_BY_FIELD_TYPE.get(field_type, PSM_BY_FIELD_TYPE["DEFAULT"])
        config = f"--oem 3 --psm {psm}"
        try:
            data = pytesseract.image_to_data(image, lang=lang_code, config=config,
                                              output_type=pytesseract.Output.DICT)
        except Exception as e:
            return OCRResult(text="", confidence=None, engine=self.name, language=language,
                              error=f"OCR failed: {e}")

        words: list[OCRWord] = []
        confidences = []
        texts = []
        n = len(data.get("text", []))
        for i in range(n):
            t = (data["text"][i] or "").strip()
            if not t:
                continue
            conf_raw = data["conf"][i]
            try:
                conf = float(conf_raw)
            except (TypeError, ValueError):
                conf = -1
            conf = conf if conf >= 0 else None
            box = [
                float(data["left"][i]), float(data["top"][i]),
                float(data["left"][i] + data["width"][i]), float(data["top"][i] + data["height"][i]),
            ]
            words.append(OCRWord(text=t, confidence=conf, box=box))
            texts.append(t)
            if conf is not None:
                confidences.append(conf)

        full_text = " ".join(texts).strip()
        mean_conf = round(sum(confidences) / len(confidences), 1) if confidences else None
        return OCRResult(text=full_text, confidence=mean_conf, words=words,
                          engine=self.name, language=language)


_engine_singleton: TesseractEngine | None = None


def get_engine() -> TesseractEngine:
    global _engine_singleton
    if _engine_singleton is None:
        _engine_singleton = TesseractEngine()
    return _engine_singleton
