# Self-hosting Emouva

Emouva is **local-first**: you run the whole stack on your own machine, connect your own
brokerage, and the AI runs on your own keys. This guide covers the full setup and the
knobs that matter.

## 1. Quickstart

Requirements: **Python 3.11+**, **Node 18+**, **Docker** (or any Postgres 14+).

```bash
git clone https://github.com/kondareddy-th/emouva.git && cd emouva

# 1) Database
docker compose up -d          # Postgres on :5432 (user aegis / changeme / db aegis)

# 2) Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then edit: JWT_SECRET + (recommended) ANTHROPIC_KEY
uvicorn app.main:app --port 8001 --reload

# 3) Frontend (new terminal)
cd frontend
npm install
npm run dev                   # http://localhost:5174 (proxies /api → :8001)
```

Tables are created automatically on first backend startup — there are no migrations to run.

## 2. First run, in order

1. **Create your user** at `http://localhost:5174/signup`.
2. **Add your Anthropic key** in Settings → **AI Token** (get one at
   [console.anthropic.com](https://console.anthropic.com/settings/keys)). This powers the
   interactive research/advisor. Also put it in `backend/.env` as `ANTHROPIC_KEY` so the
   *scheduled* jobs (agent ticks, central-pool analysis, theme monitoring) can run.
3. **Become the admin**: open `http://localhost:5174/admin` → *Request admin access*.
   On a fresh install the **first admin signup is auto-activated as root** — every later
   signup waits for your approval.
4. **Seed your central repo** (the Opportunity Pool) from the admin console: seed the
   universe, let the stats gate + LLM analysis categorize names (needs `ANTHROPIC_KEY`),
   then curate. Your agent's morning screen and Themes draw from this pool.
5. **Paper trade first**: create a paper account in Settings, write your mandate in
   Trading → Settings, and watch the Ledger.
6. **(Optional) Connect Robinhood** in Settings — the OAuth flow redirects back to your
   local backend (`localhost:8001`), and tokens never leave your machine.

## 3. Market data — free vs FMP

The provider chain is `fmp → finnhub → yfinance`, normalized to one shape.

| Setup | What you get |
|---|---|
| **No keys** (default) | Quotes, fundamentals, history via Finnhub/yfinance. Ticker search falls back to yfinance. Fair-value + screening work. |
| `FINNHUB_API_KEY` | Sturdier fallback coverage (esp. international ADRs). Free tier is fine. |
| `FMP_API_KEY` | Best data quality: reliable free-cash-flow (better DCFs), analyst price targets, stock news, earnings calendar → enables the earnings-triggered re-thesis. |

Reorder or drop vendors with `MARKET_PROVIDER_ORDER` — nothing else changes.

## 4. The community is central

The Community tab talks to **emouva.com** — one shared room for every Emouva trader,
wherever their instance runs. On a self-hosted install you'll be asked to sign in with an
emouva.com account (free) to post; your trading data stays on your machine — only what
you explicitly share (a message, a P&L card) is sent.

To point at a different hub (or your own), build the frontend with
`VITE_COMMUNITY_HOST=https://your-host`.

## 5. Safety model (read before going live)

All gates are **code, not prompts**, and fail closed:

- `LIVE_EXECUTION_ENABLED` — master gate; while `false` (default), live mode records
  intent but sends nothing.
- Per-order: symbol allowlist, per-trade cap, daily spend cap, position-concentration
  ceiling, cash floor, and your **approval threshold** — anything above it waits for you.
- `TRADING_HALT=true` — global kill switch.
- Live trades run only in Robinhood's separately-funded **agentic account**.

Recommended path: paper → small `LIVE_MAX_NOTIONAL_USD` → scale as trust builds.

## 6. Hosting it for others (personal mode)

If you deploy your instance publicly but want the trading side to yourself, set
`RESTRICT_TRADING_TO=<your-username>`. Anyone can still sign up — they land in the
community; trading/agent/themes surfaces 403 for everyone not on the list. Leave it
unset for a normal self-host.

## 7. Troubleshooting

- **AI features say "add your key"** — set it in Settings → AI Token (browser) and/or
  `ANTHROPIC_KEY` in `backend/.env` (scheduler).
- **Ticker search returns nothing** — you're keyless (yfinance fallback is best-effort);
  add `FMP_API_KEY` for proper search.
- **Robinhood connect loops back with an error** — make sure the backend runs on
  `localhost:8001` (the OAuth redirect target) and retry from Settings.
- **Ports busy** — backend `--port`, frontend `frontend/vite.config.ts` (`server.port`
  + proxy target).
