from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = ""  # Now optional; provided per-request via header
    anthropic_key: str = ""      # alt env name (ANTHROPIC_KEY) used in our .env; server-side jobs
    claude_model: str = "claude-sonnet-5"  # latest Sonnet
    cors_origins: list[str] = [
        "https://emouva.com",
        "https://www.emouva.com",
        "http://localhost:5174",
    ]
    robinhood_username: str = ""
    robinhood_password: str = ""
    app_version: str = "0.3.0"

    # ── Personal-mode gating (hosted deployments) ──
    # CSV of usernames allowed to use trading/agent/themes features. Empty (the
    # default, and what self-hosters want) = every signed-in user has full access.
    # On a personal hosted instance set e.g. RESTRICT_TRADING_TO=konda — everyone
    # else can still sign up, but only for the community.
    restrict_trading_to: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://aegis:changeme@localhost:5432/aegis"

    # JWT Auth
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 10080  # 7 days

    # ── Market data providers (resilient fallback chain; see market_providers.py) ──
    # Primary is FMP (reliable, clean USD data, analyst targets, better FCF than yfinance);
    # finnhub covers the international ADRs FMP gates; yfinance is the last-resort fallback.
    # To switch primary / drop a dead vendor, reorder MARKET_PROVIDER_ORDER (env, CSV).
    fmp_api_key: str = ""              # env FMP_API_KEY        (financialmodelingprep.com /stable)
    finnhub_api_key: str = ""          # env FINNHUB_API_KEY    (finnhub.io free 60/min)
    market_provider_order: str = "fmp,finnhub,yfinance"   # env MARKET_PROVIDER_ORDER

    # Agentic trading execution mode:
    #   dry_run — record intent, place nothing (P1 default)
    #   paper   — simulate fills at market against the real book, logged in our DB (P2, no external keys)
    #   alpaca  — real Alpaca paper brokerage (needs ALPACA_* keys)
    #   live    — real Robinhood agentic account (P3)
    agent_mode: str = "dry_run"
    alpaca_api_key_id: str = ""
    alpaca_api_secret_key: str = ""

    # ── P3 live-trading safety (all fail-closed; live places nothing unless every gate is green) ──
    # Env var names have NO prefix (this Settings has no env_prefix): TRADING_HALT,
    # LIVE_EXECUTION_ENABLED, LIVE_MAX_NOTIONAL_USD, LIVE_REQUIRE_APPROVAL.
    # Global kill switch — when True, NO live order is ever sent, regardless of mode/mandate.
    trading_halt: bool = False
    # Master enable for real-money placement (order schema confirmed 2026-07-03 via
    # tools/list). While False, live mode records intent but sends nothing (safe no-op).
    live_execution_enabled: bool = False
    # "Small caps": platform default ceiling; the per-user mandate cap overrides it.
    live_max_notional_usd: float = 100.0
    # Optional belt-and-suspenders: force human approval for EVERY live order.
    # Default off — orders under the per-user live cap auto-execute; above the
    # mandate approval_threshold they still queue for approval.
    live_require_approval: bool = False
    # Polytrade — master enable for REAL-money theme execution across users' live
    # accounts. Default OFF: theme allocations are paper-only regardless of account
    # kind. Requires live_execution_enabled first (real-money themes ride the same
    # broker path + gates). Kept separate so themes can't go live by accident.
    themes_live_enabled: bool = False


settings = Settings()
