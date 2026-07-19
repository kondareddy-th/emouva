"""Stable public identifiers.

Internal primary keys stay UUIDv4 (unchanged, zero FK blast radius). On top of
that every user gets a short, stable, non-enumerable *public* id used in API
responses, logs, and support — the human-facing handle for an account.

Format: ``u_`` + 12 Crockford base32 chars (no I/L/O/U to avoid ambiguity),
lowercase. 32^12 ≈ 1.15e18 of space — collision-free well past 10M users
(a UNIQUE index + retry-on-collision covers the birthday tail regardless).
"""
from __future__ import annotations

import secrets

# Crockford base32, minus the ambiguous I L O U — lowercase for URL-friendliness.
_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"
_LEN = 12


def gen_public_id(prefix: str = "u_") -> str:
    """A fresh public id, e.g. ``u_3k9m2xq7hp4z``. Caller must still enforce the
    UNIQUE constraint (retry on the rare collision)."""
    return prefix + "".join(secrets.choice(_ALPHABET) for _ in range(_LEN))
