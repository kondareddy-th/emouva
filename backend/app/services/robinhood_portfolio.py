"""Per-user portfolio reads via the Robinhood agentic MCP, mapped to the
dashboard's existing shapes (app/models/portfolio.py). Account-parameterized so
the UI can switch between the default account and the Agentic account.

Positions from the MCP carry symbol/quantity/avg_cost; we enrich with live
quotes (get_equity_quotes) for current_price/previous_close so the dashboard
can show market value and day change.
"""
from __future__ import annotations

from .robinhood_mcp import RobinhoodMCP, list_accounts


def _f(x, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _quote_map(quotes_result: dict) -> dict:
    """symbol -> {price, previous_close} from a get_equity_quotes() result."""
    data = quotes_result.get("data", quotes_result) if isinstance(quotes_result, dict) else {}
    results = data.get("results") or data.get("quotes") or []
    out: dict[str, dict] = {}
    for item in results:
        q = item.get("quote", item) if isinstance(item, dict) else {}
        sym = q.get("symbol")
        if sym:
            out[sym] = {
                "price": _f(q.get("last_trade_price") or q.get("last_non_reg_trade_price")),
                "previous_close": _f(q.get("previous_close") or q.get("adjusted_previous_close")),
            }
    return out


async def get_accounts(token: str) -> list[dict]:
    """Active accounts for the account switcher."""
    accts = list_accounts(await RobinhoodMCP(token).get_accounts())
    return [
        {
            "account_number": a.get("account_number"),
            "type": a.get("type"),
            "nickname": a.get("nickname"),
            "is_default": bool(a.get("is_default")),
            "is_agentic": (a.get("nickname") or "").lower() == "agentic" or bool(a.get("agentic_allowed")),
        }
        for a in accts
        if a.get("state") == "active" and not a.get("deactivated")
    ]


async def resolve_account_number(token: str, account: str | None) -> str | None:
    """Map an account selector to a number. Numeric -> used directly. Else
    'agentic'/'default'/None -> resolved from the account list."""
    if account and account.isdigit():
        return account
    accts = await get_accounts(token)
    if not accts:
        return None
    if account == "agentic":
        ag = next((a for a in accts if a["is_agentic"]), None)
        if ag:
            return ag["account_number"]
    default = next((a for a in accts if a["is_default"]), None) or accts[0]
    return default["account_number"]


async def get_positions(token: str, account_number: str) -> list[dict]:
    """Positions enriched with live quotes, in the dashboard Position shape."""
    mcp = RobinhoodMCP(token)
    raw = (await mcp.get_positions(account_number)).get("data", {}).get("positions", [])
    if not raw:
        return []
    qmap = _quote_map(await mcp.get_quotes([p["symbol"] for p in raw]))
    out: list[dict] = []
    for p in raw:
        sym = p["symbol"]
        shares = _f(p.get("quantity"))
        avg = _f(p.get("average_buy_price"))
        q = qmap.get(sym, {})
        price = q.get("price") or avg
        prev = q.get("previous_close") or price
        out.append({
            "symbol": sym, "name": sym, "shares": shares, "avg_cost": avg,
            "current_price": price, "previous_close": prev, "sector": "Unknown",
            "sparkline": [], "conviction": 3,
            "equity": round(shares * price, 2),
            "percent_change": round(((price - prev) / prev * 100) if prev else 0.0, 2),
            "equity_change": round(shares * (price - prev), 2),
        })
    return out


# Frontend range (days) -> (interval, lookback days) for get_equity_historicals.
_HIST_RANGE = {
    1: ("5minute", 4),  # look back enough to catch the last session over weekends/holidays
    7: ("hour", 7),
    30: ("day", 31),
    90: ("day", 93),
    999: ("week", 365 * 5),
}


def _hist_entries(res: dict) -> list:
    d = res.get("data", res) if isinstance(res, dict) else {}
    for key in ("results", "historicals", "entries"):
        if isinstance(d.get(key), list):
            return d[key]
    for v in (d.values() if isinstance(d, dict) else []):
        if isinstance(v, list) and v and isinstance(v[0], dict) and "symbol" in v[0]:
            return v
    return []


def _hist_bars(entry: dict) -> list:
    for v in entry.values():
        if isinstance(v, list) and v and isinstance(v[0], dict) and "begins_at" in v[0]:
            return v
    return []


async def fetch_historicals(token: str, symbols: list[str], interval: str,
                            start_time: str, bounds: str = "regular") -> dict[str, list[dict]]:
    """symbol -> list of bars [{begins_at, close_price, session}] via
    get_equity_historicals (batched <=10/call). `bounds`: regular | extended |
    24_7 (controls pre-market / after-hours inclusion). Shared by chart + risk."""
    mcp = RobinhoodMCP(token)
    out: dict[str, list[dict]] = {}
    for i in range(0, len(symbols), 10):
        res = await mcp.call_tool("get_equity_historicals", {
            "symbols": symbols[i:i + 10], "start_time": start_time,
            "interval": interval, "bounds": bounds,
        })
        for entry in _hist_entries(res):
            out[entry.get("symbol")] = _hist_bars(entry)
    return out


def _series_from_hist(shares: dict[str, float], offset: float,
                      hist: dict[str, list[dict]]) -> list[dict]:
    """Sum shares*close + offset per timestamp -> [{date, value, after_hours}].
    after_hours marks post-4pm (session == 'post')."""
    closes: dict[str, dict[str, float]] = {}
    session: dict[str, str] = {}
    for sym, bars in hist.items():
        cm: dict[str, float] = {}
        for b in bars:
            cp = b.get("close_price")
            if cp not in (None, ""):
                ts = b["begins_at"]
                cm[ts] = _f(cp)
                session.setdefault(ts, b.get("session", "reg"))
        closes[sym] = cm

    all_ts = sorted({ts for cm in closes.values() for ts in cm})
    out: list[dict] = []
    last: dict[str, float] = {}
    syms = list(shares)
    for ts in all_ts:
        total = offset
        for s in syms:
            if ts in closes.get(s, {}):
                last[s] = closes[s][ts]
            if s in last:
                total += shares[s] * last[s]
        out.append({"date": ts, "value": round(total, 2), "after_hours": session.get(ts) == "post"})
    return out


_HIST_CACHE: dict[str, tuple[float, list]] = {}


async def get_history(token: str, account_number: str, days: int) -> list[dict]:
    """Cached wrapper around the synthesized-history computation. Intraday (1D)
    is cached ~90s, longer ranges ~5 min — this makes chart range-switching
    instant and dedupes the positions/historicals fetch on repeat loads. The
    chart pins the live last point client-side, so cache lag never affects the
    headline value."""
    import time
    key = f"{account_number}:{days}"
    ttl = 90 if days == 1 else 300
    hit = _HIST_CACHE.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    result = await _compute_history(token, account_number, days)
    _HIST_CACHE[key] = (time.time(), result)
    return result


async def _compute_history(token: str, account_number: str, days: int) -> list[dict]:
    """Synthesize the account's net value over time. No portfolio-history tool
    exists, so we sum each holding's historical close x current shares and add
    cash + crypto (assumed constant over the window). Approximate for periods
    where holdings changed, but matches the broker closely for recent ranges."""
    from datetime import datetime, timedelta, timezone

    mcp = RobinhoodMCP(token)
    raw_pos = (await mcp.get_positions(account_number)).get("data", {}).get("positions", [])
    shares = {p["symbol"]: _f(p.get("quantity")) for p in raw_pos if _f(p.get("quantity")) > 0}
    if not shares:
        return []  # cash-only account (e.g. Agentic) — chart shows the flat value via the headline

    pf = (await mcp.get_portfolio(account_number)).get("data", {})
    offset = _f(pf.get("cash")) + _f(pf.get("crypto_value"))  # cash (negative under margin) + crypto
    symbols = list(shares)

    if days == 1:
        # Full trading day from local (ET) midnight: pre-market + regular +
        # after-hours, so overnight/pre-market moves show. 24_7 bounds include
        # all sessions; each point is tagged after_hours (post-4pm).
        from zoneinfo import ZoneInfo
        now_et = datetime.now(ZoneInfo("America/New_York"))
        start = (now_et.replace(hour=0, minute=0, second=0, microsecond=0)
                 .astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        hist = await fetch_historicals(token, symbols, "5minute", start, bounds="24_7")
        series = _series_from_hist(shares, offset, hist)
        if not series:  # weekend / holiday — fall back to the last session
            start = (datetime.now(timezone.utc) - timedelta(days=4)).strftime("%Y-%m-%dT%H:%M:%SZ")
            hist = await fetch_historicals(token, symbols, "5minute", start, bounds="24_7")
            series = _series_from_hist(shares, offset, hist)
            if series:
                last_date = series[-1]["date"][:10]
                series = [p for p in series if p["date"][:10] == last_date]
        return series

    interval, lookback = _HIST_RANGE.get(days, ("day", days))
    start = (datetime.now(timezone.utc) - timedelta(days=lookback)).strftime("%Y-%m-%dT%H:%M:%SZ")
    hist = await fetch_historicals(token, symbols, interval, start)
    return _series_from_hist(shares, offset, hist)


async def get_summary(token: str, account_number: str) -> dict:
    """PortfolioSummary shape. Lightweight — one MCP call (get_portfolio).
    daily_change / total_gain are recomputed on the client from positions+quotes
    (getComputedSummary), so we don't re-fetch positions here."""
    pf = (await RobinhoodMCP(token).get_portfolio(account_number)).get("data", {})
    bp = pf.get("buying_power", {})
    return {
        "total_value": _f(pf.get("total_value")),
        "daily_change": 0.0,
        "daily_change_pct": 0.0,
        "total_gain": 0.0,
        "total_gain_pct": 0.0,
        "buying_power": _f(bp.get("buying_power") if isinstance(bp, dict) else bp),
        "risk_score": 0,
        "source": "robinhood",  # via the agentic MCP
    }
