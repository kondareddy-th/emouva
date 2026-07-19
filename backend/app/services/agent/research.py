"""P4 — principle backtesting + research distillation, powered by Sonnet 5.

Three LLM-backed operations, all fail-soft (return a clear stub if no key):
  • backtest_principle — analyse a proposed/edited principle against the user's
    recent agent orders and estimate its effect (a lightweight, judgment-based
    backtest, not a full historical simulation).
  • run_screen        — the "morning screen": funnel a universe (watchlist or a
    default quality set) through circle-of-competence → margin-of-safety →
    inversion using live fundamentals, and persist an AgentScreen.
  • distill           — turn a research paper / idea (URL or pasted text) into a
    concise summary and a proposed principle for the Latticework.
"""
from __future__ import annotations

import asyncio
import json
import logging

from sqlalchemy import select

from app.harness import config as hc
from app.models.db import AgentOrder, AgentPrinciple, AgentScreen, Watchlist
from app.services.market_data import get_batch_quotes, get_company_info

logger = logging.getLogger(__name__)

# A compact default universe of understandable, high-quality compounders — used
# when the user has no watchlist. Deliberately inside a Munger "circle".
DEFAULT_UNIVERSE = ["AAPL", "MSFT", "GOOGL", "COST", "V", "MA", "UNH", "JNJ",
                    "PG", "KO", "PEP", "HD", "MCO", "BRK-B", "WMT"]


def _llm_json(system: str, user: str, tool: dict, max_tokens: int = 1200,
              temperature: float | None = None) -> dict | None:
    """One forced-tool Anthropic call → the tool input dict. None if no key/err.
    (Sonnet 5 is low-variance and deprecates `temperature`; consistency comes from
    a narrow rubric + deterministic bucketing, not a temperature knob.)"""
    if not hc.ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=hc.ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model=hc.MODEL_TICK, max_tokens=max_tokens, system=system,
            tools=[tool], tool_choice={"type": "tool", "name": tool["name"]},
            messages=[{"role": "user", "content": user}],
        )
        return next((b.input for b in resp.content if getattr(b, "type", None) == "tool_use"), None)
    except Exception as e:
        logger.warning("research LLM call failed: %s", e)
        return None


# ── on-demand TRUSTED data tool (numbers come from us, never from web search) ──
_DATA_STATS = ["revenue_growth", "earnings_growth", "gross_margins", "operating_margins", "profit_margins",
               "return_on_equity", "return_on_assets", "debt_to_equity", "current_ratio", "pe_ratio",
               "forward_pe", "market_cap"]

STOCK_DATA_TOOL = {
    "name": "get_stock_data",
    "description": ("Fetch TRUSTED, live data for a ticker from OUR OWN endpoints (yfinance-backed): current "
                    "price, key fundamentals, our conservative fair value + margin of safety, AND a price-TREND "
                    "read (falling / basing / stable / rising). Use this for ANY number — price, valuation, "
                    "fundamentals. NEVER take a price or statistic from web search; those are often stale or "
                    "wrong. Call this instead. IMPORTANT: never buy a name whose trend is 'falling' (a falling "
                    "knife) even if the margin of safety is large — wait for it to base first."),
    "input_schema": {"type": "object", "properties": {"symbol": {"type": "string", "description": "ticker"}},
                     "required": ["symbol"]},
}


def get_stock_data(symbol: str) -> dict:
    """Trusted live data for one ticker (price from a live quote, fundamentals +
    fair value from our endpoints). Backs the get_stock_data tool."""
    from app.services.market_data import get_company_info, get_batch_quotes
    from app.services import fair_value as fv_svc
    sym = (symbol or "").upper().strip()
    if not sym:
        return {"error": "no symbol"}
    info = get_company_info(sym) or {}
    q = get_batch_quotes([sym])
    price = float(q[0]["price"]) if (q and q[0].get("price")) else (info.get("current_price") or None)
    try:
        fv = fv_svc.fair_value(sym, price)
    except Exception:
        fv = {}
    try:
        from app.services.agent.trend import assess_trend
        tr = assess_trend(sym)
    except Exception:
        tr = {}
    return {"symbol": sym, "price": price,
            "fair_value_conservative": fv.get("conservative"), "margin_of_safety_pct": fv.get("margin_pct"),
            "fair_value_confident": fv.get("confident"),
            "trend": tr.get("status"), "falling_knife": tr.get("falling_knife"),
            "trend_summary": tr.get("summary"),
            "forward_eps_est": info.get("forward_eps_est"), "forward_revenue_est": info.get("forward_revenue_est"),
            "analyst_grade_trend": info.get("grade_trend"),
            "fundamentals": {k: info.get(k) for k in _DATA_STATS}}


def _llm_toolloop(system: str, user: str, final_tool: dict, use_search: bool = False,
                  max_tokens: int = 1500, max_iters: int = 5) -> dict | None:
    """Run an LLM turn where it can call get_stock_data (our TRUSTED numbers) and, when
    use_search, web_search (QUALITATIVE only) until it calls final_tool. On the LAST
    iteration final_tool is FORCED, so it always ends with a proper verdict (with its
    required reason) rather than running out of turns. Raises on API error."""
    import anthropic
    client = anthropic.Anthropic(api_key=hc.ANTHROPIC_API_KEY)
    full_tools = [STOCK_DATA_TOOL, final_tool]
    if use_search:
        full_tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}] + full_tools
    messages = [{"role": "user", "content": user}]
    for i in range(max_iters):
        if i == max_iters - 1:                       # final turn → force the verdict (no more tools)
            resp = client.messages.create(model=hc.MODEL_TICK, max_tokens=max_tokens, system=system,
                                          tools=[final_tool], tool_choice={"type": "tool", "name": final_tool["name"]},
                                          messages=messages)
        else:
            resp = client.messages.create(model=hc.MODEL_TICK, max_tokens=max_tokens,
                                          system=system, tools=full_tools, messages=messages)
        final = next((b.input for b in resp.content if getattr(b, "type", None) == "tool_use"
                      and getattr(b, "name", None) == final_tool["name"]), None)
        if final is not None:
            return final
        results = []
        for b in resp.content:
            if getattr(b, "type", None) == "tool_use" and getattr(b, "name", None) == "get_stock_data":
                results.append({"type": "tool_result", "tool_use_id": b.id,
                                "content": json.dumps(get_stock_data(b.input.get("symbol", "")), default=str)})
        messages.append({"role": "assistant", "content": resp.content})
        messages.append({"role": "user", "content": results or f"Now call {final_tool['name']} with your verdict."})
    return None


def _llm_verify(system: str, user: str, tool: dict, max_tokens: int = 1500) -> dict | None:
    """The double-check pass. Web search (qualitative) + our get_stock_data tool
    (trusted numbers), degrading to data-tool-only then a forced structured verdict.
    Never hard-fails."""
    if not hc.ANTHROPIC_API_KEY:
        return None
    try:
        out = _llm_toolloop(system, user, tool, use_search=True, max_tokens=max_tokens)
        if out is not None:
            return out
    except Exception as e:                       # web search likely unavailable on this account
        logger.info("verify web-search unavailable (%s) — data-tool only", e)
    try:
        out = _llm_toolloop(system, user, tool, use_search=False, max_tokens=max_tokens)
        if out is not None:
            return out
    except Exception as e:
        logger.warning("verify data-tool loop failed: %s", e)
    return _llm_json(system, user, tool, max_tokens)   # last resort: forced verdict on inline data


# ── Message Batches API ─────────────────────────────────────────────────────
# For bulk, offline jobs (the central pool analysis) the Batches API is the right
# tool: ~50% cheaper than serial calls and it scales to the whole S&P 500 in one
# submission instead of hundreds of latency-bound sequential requests.

def _batch_request(custom_id: str, system: str, user: str, tool: dict, max_tokens: int) -> dict:
    """One forced-tool request in the shape the Batches API expects."""
    return {
        "custom_id": custom_id,
        "params": {
            "model": hc.MODEL_TICK, "max_tokens": max_tokens, "system": system,
            "tools": [tool], "tool_choice": {"type": "tool", "name": tool["name"]},
            "messages": [{"role": "user", "content": user}],
        },
    }


def _run_batch_sync(requests: list[dict], poll_interval: int, timeout: int) -> dict:
    """Submit a batch, poll until it ends, return {custom_id: tool_input|None}.
    Blocking — call via asyncio.to_thread."""
    import time
    import anthropic
    client = anthropic.Anthropic(api_key=hc.ANTHROPIC_API_KEY)
    batch = client.messages.batches.create(requests=requests)
    bid = batch.id
    logger.info("batch %s submitted: %d requests", bid, len(requests))
    waited = 0
    while waited < timeout:
        b = client.messages.batches.retrieve(bid)
        if b.processing_status == "ended":
            break
        time.sleep(poll_interval)
        waited += poll_interval
    else:
        logger.warning("batch %s timed out after %ds (status not ended)", bid, timeout)
        return {"__batch_id__": bid}
    out: dict = {"__batch_id__": bid}
    for entry in client.messages.batches.results(bid):
        r = entry.result
        if r.type != "succeeded":
            out[entry.custom_id] = None
            continue
        out[entry.custom_id] = next(
            (blk.input for blk in r.message.content if getattr(blk, "type", None) == "tool_use"), None)
    return out


async def run_batch_json(items: list[tuple], tool: dict, max_tokens: int = 1200,
                         poll_interval: int = 20, timeout: int = 5400) -> dict:
    """items = [(custom_id, system, user), …] → {custom_id: tool_input dict | None}.
    Returns {} if no key / no items. Extra key '__batch_id__' carries the batch id."""
    if not hc.ANTHROPIC_API_KEY or not items:
        return {}
    requests = [_batch_request(cid, system, user, tool, max_tokens) for cid, system, user in items]
    return await asyncio.to_thread(_run_batch_sync, requests, poll_interval, timeout)


# ── principle backtest ──────────────────────────────────────────────────────

_BACKTEST_TOOL = {
    "name": "backtest_result",
    "description": "Structured estimate of a principle's effect on recent trading.",
    "input_schema": {
        "type": "object",
        "properties": {
            "trades_reviewed": {"type": "integer"},
            "would_block": {"type": "integer", "description": "recent orders this principle would have blocked or changed"},
            "pnl_effect": {"type": "string", "description": "short estimate, e.g. '+$310 avoided' or 'neutral'"},
            "drawdown_effect": {"type": "string", "description": "e.g. '−0.4pp' or 'negligible'"},
            "restate": {"type": "string", "description": "how the agent will apply this, in one sentence"},
            "verdict": {"type": "string", "description": "1–2 sentence recommendation (adopt / revise / discard and why)"},
            "recommend_adopt": {"type": "boolean"},
        },
        "required": ["trades_reviewed", "would_block", "verdict", "restate", "recommend_adopt"],
    },
}


async def backtest_principle(db, user_id, text: str, section: str = "Selection") -> dict:
    """Judge a proposed principle against the user's recent agent orders."""
    rows = (await db.execute(
        select(AgentOrder).where(AgentOrder.user_id == user_id)
        .order_by(AgentOrder.created_at.desc()).limit(25)
    )).scalars().all()
    trades = [f"{o.side.upper()} {o.qty:g} {o.symbol} ~${o.est_notional:,.0f} [{o.status}] — {(o.rationale or '')[:120]}"
              for o in rows]
    trades_txt = "\n".join(trades) or "No agent orders yet."
    system = ("You are the risk-and-principles analyst for a patient, Munger-style value agent. "
              "Given a proposed principle and the agent's recent orders, estimate how the principle "
              "would have changed behaviour. Be honest and specific; prefer 'revise' or 'discard' when "
              "a principle is vague, redundant, or harmful. Call backtest_result.")
    user = (f"PROPOSED PRINCIPLE ({section}):\n{text}\n\nRECENT AGENT ORDERS (newest first):\n{trades_txt}\n\n"
            "Estimate its effect and give a verdict.")
    out = await asyncio.to_thread(_llm_json, system, user, _BACKTEST_TOOL)
    if not out:
        return {"trades_reviewed": len(rows), "would_block": 0, "pnl_effect": "n/a", "drawdown_effect": "n/a",
                "restate": "Enforced as written.", "verdict": "Backtest unavailable (no model key) — adopt at your discretion.",
                "recommend_adopt": True, "stub": True}
    out.setdefault("trades_reviewed", len(rows))
    return out


# ── morning screen ──────────────────────────────────────────────────────────

_SCREEN_TOOL = {
    "name": "screen_result",
    "description": "The morning-screen funnel result.",
    "input_schema": {
        "type": "object",
        "properties": {
            "stages": {
                "type": "array",
                "description": "Funnel stages from widest to narrowest.",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "count": {"type": "integer"},
                        "tickers": {"type": "array", "items": {"type": "string"}},
                        "exclusions": {"type": "array", "items": {"type": "string"},
                                       "description": "e.g. 'NVDA — outside circle; hard to value'"},
                    },
                    "required": ["label", "count", "tickers"],
                },
            },
            "survivor": {"type": ["string", "null"], "description": "the single best candidate ticker, or null if none clears"},
            "verdict": {"type": "string", "description": "2–4 sentences: the survivor's thesis, margin of safety, inversion check, and whether to act"},
        },
        "required": ["stages", "verdict"],
    },
}


def _fundamentals(symbols: list[str]) -> list[dict]:
    """Compact fundamentals per symbol for the screen prompt (sync; yfinance)."""
    quotes = {q["symbol"]: q for q in get_batch_quotes(symbols)}
    out = []
    for s in symbols:
        info = get_company_info(s) or {}
        price = float(quotes.get(s, {}).get("price") or info.get("current_price") or 0)
        tgt = info.get("target_mean_price")
        mos = round((tgt - price) / tgt * 100, 1) if (tgt and price) else None  # analyst-target proxy for margin of safety
        out.append({
            "symbol": s, "name": info.get("name") or s, "sector": info.get("sector"),
            "price": price, "pe": info.get("pe_ratio"), "forward_pe": info.get("forward_pe"),
            "peg": info.get("peg_ratio"), "roe": info.get("return_on_equity"),
            "gross_margin": info.get("gross_margins"), "target_mean": tgt,
            "margin_of_safety_pct": mos, "rec": info.get("recommendation_key"),
        })
    return out


async def run_screen(db, user, token: str | None, account: str, mos_floor: float = 30.0,
                     mandate=None) -> AgentScreen:
    """Run the morning screen. Universe = the shared opportunity pool, pre-filtered
    by the user's margin of safety + circle + current holdings; falls back to the
    watchlist / default quality set if the pool is empty. LLM funnel via Sonnet 5."""
    from app.services.agent import discovery

    # holdings on the active account — don't re-surface what we already own
    held: set[str] = set()
    try:
        if account and account.endswith("-paper"):
            from app.services import accounts as acct_svc
            held = {p["symbol"] for p in await acct_svc.get_positions(db, account)}
        elif token and account:
            from app.services import robinhood_portfolio as rp
            held = {p["symbol"] for p in await rp.get_positions(token, account)}
    except Exception:
        pass

    inc = (getattr(mandate, "circle_include", None) or None)
    exc = (getattr(mandate, "circle_exclude", None) or None)
    pool = await discovery.list_pool(db, min_margin=mos_floor, confident_only=True,
                                     exclude_symbols=held, sectors_in=inc, sectors_out=exc, limit=25)
    if pool:
        universe = [p.symbol for p in pool]
        fundamentals = [{"symbol": p.symbol, "name": p.name, "sector": p.sector, "price": p.last_price,
                         "margin_of_safety_pct": p.margin_pct, "fair_value": p.fv_conservative,
                         "why": f"down {p.pct_change}% ({p.source})"} for p in pool]
    else:
        wl = (await db.execute(select(Watchlist.symbol).where(Watchlist.user_id == user.id))).scalars().all()
        universe = [s.upper() for s in wl][:20] or DEFAULT_UNIVERSE
        fundamentals = await asyncio.to_thread(_fundamentals, universe)

    system = ("You are a patient, Munger-style value analyst running a morning screen. Funnel the "
              "universe through: (1) circle of competence — drop what's genuinely hard to value; "
              f"(2) margin of safety ≥ {mos_floor:.0f}% (use margin_of_safety_pct); (3) inversion — "
              "for the finalists, try to kill the thesis and drop any that fail. Then pick at most one "
              "survivor. Buy rarely; it's fine to end with no survivor. Call screen_result with the stages.")
    user_msg = (f"UNIVERSE ({len(universe)} names) with fundamentals:\n{json.dumps(fundamentals, default=str)}\n\n"
                f"Margin-of-safety floor: {mos_floor:.0f}%. Run the funnel.")
    out = await asyncio.to_thread(_llm_json, system, user_msg, _SCREEN_TOOL, max_tokens=1600)

    if not out:
        out = {"stages": [{"label": "Universe", "count": len(universe), "tickers": universe, "exclusions": []}],
               "survivor": None, "verdict": "Screen unavailable (no model key)."}
    screen = AgentScreen(
        user_id=user.id, account=account, universe_count=len(universe),
        stages=out.get("stages", []), survivor=out.get("survivor"),
        verdict=out.get("verdict", ""),
    )
    db.add(screen)
    await db.commit()
    await db.refresh(screen)
    return screen


# ── research distillation ───────────────────────────────────────────────────

_DISTILL_TOOL = {
    "name": "distilled",
    "description": "A research idea distilled into a summary and a candidate principle.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "gist": {"type": "string", "description": "2–3 sentence plain-language summary of the finding"},
            "inversion": {"type": "string", "description": "when this idea FAILS / its limits"},
            "principle": {"type": "string", "description": "one crisp principle to add to the Latticework, in the user's voice"},
            "section": {"type": "string", "enum": ["Temperament", "Selection", "Sizing & Selling"]},
        },
        "required": ["title", "gist", "principle", "section"],
    },
}


async def _fetch_url_text(url: str) -> str:
    import httpx, re
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
            r = await c.get(url, headers={"User-Agent": "emouva-research/0.1"})
        text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", r.text, flags=re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text)[:12000]
    except Exception as e:
        logger.warning("distill fetch failed: %s", e)
        return ""


_ASSESS_TOOL = {
    "name": "track_assessment",
    "description": "Decide whether a watched stock, now in an interesting valuation range, should be proposed to the user.",
    "input_schema": {
        "type": "object",
        "properties": {
            "recommend": {"type": "boolean", "description": "true only if it genuinely fits and you'd propose the buy"},
            "thesis": {"type": "string", "description": "the one-paragraph thesis if recommending (why own it)"},
            "rationale": {"type": "string", "description": "1–2 sentences: the decision and its key reason (or why not)"},
            "confidence": {"type": "number", "description": "0..1"},
        },
        "required": ["recommend", "rationale", "confidence"],
    },
}


async def assess_track(symbol: str, fv: dict, principles_block: str, fundamentals: dict | None = None) -> dict:
    """Harness deep-dive on a tracked name that just entered an interesting range.
    Skeptical by default — proposes only a genuine fit. Returns track_assessment."""
    system = ("You are 'the Partner', a patient Munger-style value investor. The user asked to WATCH this "
              "stock; it has now reached a margin of safety against a conservative fair value. Decide, honestly "
              "and skeptically, whether to propose it for the user's approval. Honor the Latticework below. "
              "Invert first — try to kill it — and recommend only what survives. Call track_assessment.")
    user = (f"SYMBOL: {symbol}\nFAIR VALUE (conservative ${fv.get('conservative')}, base ${fv.get('base')}, "
            f"range ${fv.get('low')}–${fv.get('high')}); current ${fv.get('current_price')}; "
            f"margin of safety {fv.get('margin_pct')}%.\n"
            f"FUNDAMENTALS: {json.dumps(fundamentals or {}, default=str)[:1500]}\n\n"
            f"THE LATTICEWORK (honor these):\n{principles_block or '(none yet)'}\n\nAssess and decide.")
    out = await asyncio.to_thread(_llm_json, system, user, _ASSESS_TOOL, 1200)
    if not out:
        return {"recommend": False, "rationale": "Assessment unavailable (no model key).", "confidence": 0.0, "stub": True}
    return out


async def distill(source: str) -> dict:
    """source: a URL or pasted text → {title, gist, inversion, principle, section}."""
    body = source
    if source.strip().startswith("http"):
        fetched = await _fetch_url_text(source.strip())
        body = fetched or source
    system = ("You distill investing research into the Latticework of a patient, Munger-style value "
              "agent. Summarize faithfully, note when the idea fails (inversion), and propose ONE crisp, "
              "actionable principle. Call distilled.")
    out = await asyncio.to_thread(_llm_json, system, f"RESEARCH SOURCE:\n{body[:12000]}", _DISTILL_TOOL)
    if not out:
        return {"title": "Distillation unavailable", "gist": "No model key configured.",
                "inversion": "", "principle": "", "section": "Selection", "stub": True}
    return out
