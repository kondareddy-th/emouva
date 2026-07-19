"""Robinhood agentic MCP — OAuth 2.1 (auth-code + PKCE + Dynamic Client Registration).

Replaces the old robin_stocks username/password login with the official, sanctioned
OAuth flow. Endpoints were discovered live from the MCP server's OAuth metadata
(/.well-known/oauth-authorization-server/mcp/trading):

    authorization_endpoint : https://robinhood.com/oauth
    token_endpoint         : https://api.robinhood.com/oauth2/token/
    registration_endpoint  : https://agent.robinhood.com/oauth/trading/register  (DCR)
    resource (MCP)         : https://agent.robinhood.com/mcp/trading
    grant types            : authorization_code, refresh_token
    PKCE                   : S256 (required)   |   public client (no secret)
    scope                  : internal

Flow:
    1. register_client()  -> client_id (DCR; cached per redirect_uri)
    2. build_authorize_url(...) -> send the user to Robinhood to approve
    3. exchange_code(...) -> access_token + refresh_token
    4. refresh(...)       -> new access_token when it expires
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from pathlib import Path

import httpx

# Discovered OAuth endpoints (stable defaults; refreshed by discover() if needed).
RESOURCE = "https://agent.robinhood.com/mcp/trading"
AUTHORIZE_ENDPOINT = "https://robinhood.com/oauth"
TOKEN_ENDPOINT = "https://api.robinhood.com/oauth2/token/"
REGISTRATION_ENDPOINT = "https://agent.robinhood.com/oauth/trading/register"
METADATA_URL = "https://agent.robinhood.com/.well-known/oauth-authorization-server/mcp/trading"
SCOPE = "internal"

REDIRECT_URI = os.getenv("EMOUVA_RH_REDIRECT_URI", "http://localhost:8001/api/robinhood/callback")
# Where we cache the DCR client registration so we don't re-register every boot.
_CLIENT_CACHE = Path(os.getenv("EMOUVA_RH_CLIENT_CACHE",
                               Path(__file__).resolve().parents[2] / ".robinhood_client.json"))


# --- PKCE ---------------------------------------------------------------------
def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def make_pkce() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) using S256."""
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


def make_state() -> str:
    return _b64url(secrets.token_bytes(16))


# --- Dynamic Client Registration ---------------------------------------------
async def register_client(redirect_uri: str = REDIRECT_URI) -> str:
    """Register (or load cached) OAuth client for `redirect_uri`; return client_id."""
    if os.getenv("EMOUVA_RH_CLIENT_ID"):
        return os.environ["EMOUVA_RH_CLIENT_ID"]
    if _CLIENT_CACHE.is_file():
        cached = json.loads(_CLIENT_CACHE.read_text())
        if cached.get("redirect_uri") == redirect_uri and cached.get("client_id"):
            return cached["client_id"]

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(REGISTRATION_ENDPOINT, json={
            "client_name": "Emouva",
            "redirect_uris": [redirect_uri],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
            "scope": SCOPE,
        })
        resp.raise_for_status()
        client_id = resp.json()["client_id"]

    _CLIENT_CACHE.write_text(json.dumps({"client_id": client_id, "redirect_uri": redirect_uri}))
    return client_id


# --- Authorization + token ----------------------------------------------------
def build_authorize_url(client_id: str, state: str, code_challenge: str,
                        redirect_uri: str = REDIRECT_URI) -> str:
    from urllib.parse import urlencode
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": SCOPE,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTHORIZE_ENDPOINT}?{urlencode(params)}"


async def exchange_code(code: str, code_verifier: str, client_id: str,
                        redirect_uri: str = REDIRECT_URI) -> dict:
    """Exchange an auth code for tokens. Returns the token response dict."""
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(TOKEN_ENDPOINT, data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "code_verifier": code_verifier,
        })
        resp.raise_for_status()
        return resp.json()


async def refresh(refresh_token: str, client_id: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(TOKEN_ENDPOINT, data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        })
        resp.raise_for_status()
        return resp.json()
