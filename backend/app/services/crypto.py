"""Symmetric encryption for secrets at rest (Robinhood OAuth tokens).

Key derives from EMOUVA_TOKEN_KEY if set, else from JWT_SECRET, so there's no new
secret to manage in dev. Set a dedicated EMOUVA_TOKEN_KEY in production.
"""
from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet

from app.config import settings


def _fernet() -> Fernet:
    raw = os.getenv("EMOUVA_TOKEN_KEY") or settings.jwt_secret or "dev-insecure-key"
    key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
    return Fernet(key)


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
