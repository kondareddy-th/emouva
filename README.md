<div align="center">

# ◆ Emouva

**An open-source, local-first AI agent that trades your portfolio the way the best investors actually work — and a community to share P&L and learn from other AI traders.**

*Screen everything · buy rarely · explain every move · you hold the mandate.*

[emouva.com](https://emouva.com) · MIT licensed · Bring your own keys

</div>

---

## What is this?

Emouva gives you a personal AI "Partner" that runs a disciplined, value-investing process over your portfolio: it screens the market on a cadence, forms a falsifiable thesis for anything it wants to own, sizes positions against hard risk limits, and asks your permission before anything over your threshold. Most days it does nothing — that's the point.

It runs **on your own machine** against your **own brokerage and AI keys**. Nothing is sent to a server you don't control. [emouva.com](https://emouva.com) is the **community** — a place to post your P&L (as a one-tap "Wrapped"-style card), swap tricks, and see how others run their agents.

> **Why local-first?** Brokerages don't hand out agent access to arbitrary third-party websites. So instead of hosting the trader, you run it yourself — the OAuth flow redirects to your own `localhost`, your tokens stay on your box, and the AI runs on your key.

## Features

- **The Partner** — an hourly agent loop: reconcile → check theses → propose at most one high-conviction trade, every move logged to a transparent Ledger.
- **Value-investing brain** — DCF + analyst + earnings fair-value triangulation, a margin-of-safety gate, a "Living Thesis" with machine-checkable falsifiers and a 4-lens red-team, plus guards against catastrophic drawdowns and momentum "falling knives."
- **Paper first** — the same brain runs on simulated money before you ever risk real capital.
- **Polytrade** — AI-curated thematic baskets you fund in one tap, auto-managed and auto-exited when the thesis breaks.
- **Community + P&L Wrapped** — share a custom-built P&L card to the community feed with one click.
- **Bring your own keys (BYOK)** — your Anthropic key powers the AI; your brokerage connection is yours alone.

## Stack

| Layer | Tech |
|---|---|
| Backend | Python · FastAPI · SQLAlchemy (async) · PostgreSQL |
| Frontend | React · TypeScript · Vite |
| AI | Anthropic Claude (your key) |
| Brokerage | Robinhood agentic MCP over OAuth 2.1 (PKCE + Dynamic Client Registration) |
| Market data | FMP → Finnhub → yfinance fallback chain |

## Quickstart (local)

Requires **Python 3.13+**, **Node 18+**, and a **PostgreSQL** database.

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# configure (see below), then:
uvicorn app.main:app --port 8001 --reload
```

Create `backend/.env`:

```ini
DATABASE_URL=postgresql+asyncpg://USER:PASS@localhost:5432/emouva
JWT_SECRET=change-me
# Market data (optional but recommended)
FMP_API_KEY=...
FINNHUB_API_KEY=...
# Robinhood OAuth redirects back to your local backend:
EMOUVA_RH_REDIRECT_URI=http://localhost:8001/api/robinhood/callback
```

> You do **not** need an `ANTHROPIC_KEY` on the server — each user supplies their own in the app (Settings → **AI Token**), sent per-request. A server key is only used for hosted deployments.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5174
```

### 3. Connect & go

1. Open the app, create an account, and go to **Settings**.
2. Paste your **Anthropic API key** under *AI Token* (get one at [console.anthropic.com](https://console.anthropic.com/settings/keys)) — it's stored only in your browser.
3. Click **Connect Robinhood** — you'll authorize via Robinhood's official agent flow; the callback returns to your local `localhost:8001`.
4. Start on **paper money**, write your mandate, and watch the Ledger.

## Disclaimer

Emouva is a technology tool, **not** a registered investment adviser, and nothing here is investment advice. Live markets involve risk, including loss of principal. Paper trading is simulated. Use at your own risk.

## License

[MIT](./LICENSE) © 2026 Kondareddy Thanigundala
