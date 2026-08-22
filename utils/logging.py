"""
Privacy-aware logging.

Per the app's privacy requirements: never print citizenship numbers or other
sensitive extracted OCR output to the console/log file. This module gives
the rest of the codebase a single place to log through, with a redaction
helper so a stray `log.info(f"citizenship no: {value}")` doesn't leak PII
into logs by accident.
"""
from __future__ import annotations

import logging
import sys

_SENSITIVE_KEYS = {
    "citizenship_number", "citizenship_no", "national_id_no", "passport_no",
    "pan_number", "id_number", "id_no", "dob", "date_of_birth",
}


def redact(value: str, keep: int = 2) -> str:
    """Mask a sensitive string, keeping only the first/last `keep` characters."""
    if value is None:
        return ""
    s = str(value)
    if len(s) <= keep * 2:
        return "*" * len(s)
    return f"{s[:keep]}{'*' * (len(s) - keep * 2)}{s[-keep:]}"


def redact_field(field_name: str, value: str) -> str:
    """Redact `value` automatically if `field_name` looks sensitive."""
    if field_name and field_name.lower() in _SENSITIVE_KEYS:
        return redact(value)
    return value


def get_logger(name: str = "kyc_validator") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S"
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
