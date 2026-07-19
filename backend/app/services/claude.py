"""
Claude API service — async wrapper around the Anthropic SDK.
All AI interactions flow through this single service.
API key is provided per-request from the user's browser.
"""

import json
import logging
from collections.abc import AsyncIterator

from anthropic import AsyncAnthropic

from app.config import settings
from app.prompts import (
    STOCK_ANALYZER_SYSTEM,
    BEAR_CASE_SYSTEM,
    THESIS_GENERATOR_SYSTEM,
    DAILY_BRIEF_SYSTEM,
    SENTIMENT_SYSTEM,
    ADVISOR_SYSTEM,
    FULL_REPORT_SYSTEM,
)

logger = logging.getLogger(__name__)


def _get_client(api_key: str) -> AsyncAnthropic:
    """Create an Anthropic client with the server API key."""
    return AsyncAnthropic(api_key=api_key)


async def _call_claude(
    system: str,
    user_message: str,
    api_key: str,
    max_tokens: int = 4096,
    model: str | None = None,
    web_search: bool = False,
) -> str:
    """Low-level Claude API call. When web_search=True, the model may run live internet
    searches (Anthropic server tool) for the latest developments before answering — we
    handle pause_turn continuations and return the FINAL text block (past any search
    blocks), so structured-JSON callers still get clean output."""
    client = _get_client(api_key)
    kwargs: dict = {"model": model or settings.claude_model, "max_tokens": max_tokens, "system": system}
    if web_search:
        kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 4}]
    messages = [{"role": "user", "content": user_message}]
    collected: list[str] = []            # accumulate text across pause_turn continuations
    for _ in range(6):   # web_search can return pause_turn — continue until the model finishes
        message = await client.messages.create(messages=messages, **kwargs)
        # A web_search response interleaves text with search blocks and can split the answer
        # across pause_turn turns — keep ALL text blocks so structured JSON isn't left truncated.
        collected += [b.text for b in message.content
                      if getattr(b, "type", None) == "text" and getattr(b, "text", None)]
        if getattr(message, "stop_reason", None) == "pause_turn":
            messages.append({"role": "assistant", "content": message.content})
            continue
        break
    # Join with "" (NOT "\n"): when web_search splits the answer, the text blocks are a
    # continuous stream — a newline between them would land inside a JSON string and break parsing.
    return "".join(collected).strip()


async def _stream_claude(
    system: str,
    user_message: str,
    api_key: str,
    max_tokens: int = 4096,
    model: str | None = None,
) -> AsyncIterator[str]:
    """Stream Claude response token-by-token. Yields text delta strings."""
    client = _get_client(api_key)
    async with client.messages.stream(
        model=model or settings.claude_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        async for text in stream.text_stream:
            yield text


async def _stream_claude_messages(
    system: str,
    messages: list[dict],
    api_key: str,
    max_tokens: int = 4096,
    model: str | None = None,
) -> AsyncIterator[str]:
    """Stream Claude response for a multi-turn conversation. Yields text deltas."""
    client = _get_client(api_key)
    async with client.messages.stream(
        model=model or settings.claude_model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield text


# ── Data Enrichment Helpers ────────────────────────────────────

# Module-level buffer: stores raw enrichment data for DB cache write-through
_enrichment_buffer: dict[str, dict] = {}


async def flush_enrichment_to_cache(ticker: str) -> None:
    """Write buffered enrichment data (company_info, earnings, news, market_data) to stock_metrics DB."""
    data = _enrichment_buffer.pop(ticker.upper(), None)
    if not data:
        return
    try:
        from app.database import async_session
        from app.services.stock_cache import upsert_field
        async with async_session() as db:
            for field_name in ("company_info", "earnings", "news", "market_data"):
                if data.get(field_name):
                    await upsert_field(db, ticker, field_name, data[field_name])
    except Exception:
        logger.warning("Failed to flush enrichment cache for %s", ticker)


def _extract_financials(ticker: str) -> list[dict]:
    """Extract key financial metrics from yfinance for the Financials tab."""
    try:
        from app.services.market_data import get_company_info
        info = get_company_info(ticker)
        if not info:
            return []

        def _fmt_large(v: float | None) -> str | None:
            if v is None:
                return None
            av = abs(v)
            if av >= 1e12:
                return f"${v / 1e12:.1f}T"
            if av >= 1e9:
                return f"${v / 1e9:.1f}B"
            if av >= 1e6:
                return f"${v / 1e6:.0f}M"
            return f"${v:,.0f}"

        def _fmt_pct(v: float | None) -> str | None:
            if v is None:
                return None
            return f"{v * 100:.1f}%"

        def _trend(v: float | None) -> str:
            if v is None:
                return "flat"
            return "up" if v > 0 else "down" if v < 0 else "flat"

        metrics: list[dict] = []

        # Revenue & Earnings
        if info.get("total_revenue"):
            metrics.append({"metric": "Revenue (TTM)", "value": _fmt_large(info["total_revenue"]), "trend": _trend(info.get("revenue_growth"))})
        if info.get("net_income"):
            metrics.append({"metric": "Net Income (TTM)", "value": _fmt_large(info["net_income"]), "trend": _trend(info.get("earnings_growth"))})
        if info.get("free_cash_flow"):
            metrics.append({"metric": "Free Cash Flow", "value": _fmt_large(info["free_cash_flow"]), "trend": "up" if info["free_cash_flow"] > 0 else "down"})

        # Margins
        if info.get("gross_margins"):
            metrics.append({"metric": "Gross Margin", "value": _fmt_pct(info["gross_margins"]), "trend": "up" if info["gross_margins"] > 0.4 else "flat"})
        if info.get("operating_margins"):
            metrics.append({"metric": "Operating Margin", "value": _fmt_pct(info["operating_margins"]), "trend": "up" if info["operating_margins"] > 0.15 else "flat"})
        if info.get("profit_margins"):
            metrics.append({"metric": "Net Margin", "value": _fmt_pct(info["profit_margins"]), "trend": "up" if info["profit_margins"] > 0.1 else "flat"})

        # Growth
        if info.get("revenue_growth"):
            metrics.append({"metric": "Revenue Growth (YoY)", "value": _fmt_pct(info["revenue_growth"]), "trend": _trend(info["revenue_growth"])})
        if info.get("earnings_growth"):
            metrics.append({"metric": "Earnings Growth (YoY)", "value": _fmt_pct(info["earnings_growth"]), "trend": _trend(info["earnings_growth"])})

        # Valuation
        if info.get("pe_ratio"):
            metrics.append({"metric": "P/E (TTM)", "value": f"{info['pe_ratio']:.1f}x", "trend": "flat"})
        if info.get("forward_pe"):
            metrics.append({"metric": "Forward P/E", "value": f"{info['forward_pe']:.1f}x", "trend": "flat"})
        if info.get("price_to_sales"):
            metrics.append({"metric": "P/S Ratio", "value": f"{info['price_to_sales']:.1f}x", "trend": "flat"})

        # Per-share
        if info.get("eps_trailing"):
            metrics.append({"metric": "EPS (TTM)", "value": f"${info['eps_trailing']:.2f}", "trend": _trend(info.get("earnings_growth"))})

        # Balance Sheet
        if info.get("total_cash"):
            metrics.append({"metric": "Cash on Hand", "value": _fmt_large(info["total_cash"]), "trend": "up"})
        if info.get("total_debt"):
            metrics.append({"metric": "Total Debt", "value": _fmt_large(info["total_debt"]), "trend": "down"})
        if info.get("debt_to_equity") is not None:
            metrics.append({"metric": "Debt/Equity", "value": f"{info['debt_to_equity']:.1f}%", "trend": "up" if info["debt_to_equity"] < 50 else "down"})

        # Returns
        if info.get("return_on_equity"):
            metrics.append({"metric": "ROE", "value": _fmt_pct(info["return_on_equity"]), "trend": "up" if info["return_on_equity"] > 0.15 else "flat"})

        # --- Quality Metrics (from advanced enrichment) ---
        try:
            from app.services.market_data import get_annual_financials, compute_piotroski_score, get_peer_comparison

            # ROIC & FCF Yield from annual data
            annual_data = get_annual_financials(ticker)
            if annual_data.get("annual") and len(annual_data["annual"]) > 0:
                latest = annual_data["annual"][0]
                if latest.get("roic"):
                    label = "Excellent" if latest["roic"] > 0.15 else "Good" if latest["roic"] > 0.10 else "Below avg"
                    metrics.append({"metric": "ROIC", "value": f"{latest['roic'] * 100:.1f}%", "trend": "up" if latest["roic"] > 0.15 else "flat", "badge": label})
                if latest.get("fcf_yield"):
                    label = "Attractive" if latest["fcf_yield"] > 0.05 else "Fair" if latest["fcf_yield"] > 0.02 else "Low"
                    metrics.append({"metric": "FCF Yield", "value": f"{latest['fcf_yield'] * 100:.2f}%", "trend": "up" if latest["fcf_yield"] > 0.03 else "flat", "badge": label})

            # Piotroski F-Score
            pio = compute_piotroski_score(ticker)
            if pio.get("score") is not None:
                label = "Strong" if pio["score"] >= 7 else "Moderate" if pio["score"] >= 4 else "Weak"
                metrics.append({"metric": "Piotroski F-Score", "value": f"{pio['score']}/9", "trend": "up" if pio["score"] >= 7 else "flat" if pio["score"] >= 4 else "down", "badge": label})

            # Peer P/E comparison
            peers = get_peer_comparison(ticker)
            if peers.get("pe_vs_sector") is not None:
                prem = peers["pe_vs_sector"]
                label = f"{abs(prem):.0f}% {'premium' if prem > 0 else 'discount'}"
                metrics.append({"metric": "P/E vs Sector", "value": label, "trend": "up" if prem < 0 else "down" if prem > 20 else "flat"})
        except Exception:
            pass  # Advanced metrics are best-effort

        return metrics
    except Exception:
        logger.warning("Failed to extract financials for %s", ticker)
        return []


def _build_enrichment(ticker: str, fresh: bool = False) -> tuple[str, float | None]:
    """Build comprehensive data enrichment string for a ticker. Returns (enrichment_text, current_price).
    Set fresh=True to bypass cache and fetch latest data (use for user-triggered deep analysis).
    Also buffers raw data for DB cache write-through (call flush_enrichment_to_cache() afterwards).
    """
    current_price = None
    prev_close = None
    try:
        from app.services.market_data import get_earnings, get_company_info, get_news, invalidate_cache

        if fresh:
            invalidate_cache(ticker)

        info = get_company_info(ticker)
        earnings = get_earnings(ticker, years=2)
        news = get_news(ticker)

        parts = []

        # --- Live Price ---
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            fast_info = t.fast_info
            current_price = getattr(fast_info, "last_price", None)
            prev_close = getattr(fast_info, "previous_close", None)
            if current_price:
                change = ""
                if prev_close and prev_close > 0:
                    pct = ((current_price - prev_close) / prev_close) * 100
                    change = f" ({'+' if pct >= 0 else ''}{pct:.2f}% today)"
                parts.append(f"Current Price: ${current_price:.2f}{change}")
        except Exception:
            pass

        # --- Company Profile ---
        profile_parts = []
        if info.get("sector"):
            profile_parts.append(f"Sector: {info['sector']} | Industry: {info.get('industry', 'N/A')}")
        if info.get("market_cap"):
            parts.append(f"Market Cap: ${info['market_cap']:,.0f}")
        if info.get("full_time_employees"):
            profile_parts.append(f"Employees: {info['full_time_employees']:,}")
        if profile_parts:
            parts.extend(profile_parts)

        # --- Valuation Metrics ---
        val_parts = []
        if info.get("pe_ratio"):
            val_parts.append(f"P/E (TTM): {info['pe_ratio']:.1f}")
        if info.get("forward_pe"):
            val_parts.append(f"Forward P/E: {info['forward_pe']:.1f}")
        if info.get("peg_ratio"):
            val_parts.append(f"PEG Ratio: {info['peg_ratio']:.2f}")
        if info.get("price_to_book"):
            val_parts.append(f"P/B: {info['price_to_book']:.2f}")
        if info.get("price_to_sales"):
            val_parts.append(f"P/S: {info['price_to_sales']:.2f}")
        if info.get("enterprise_to_ebitda"):
            val_parts.append(f"EV/EBITDA: {info['enterprise_to_ebitda']:.1f}")
        if info.get("enterprise_to_revenue"):
            val_parts.append(f"EV/Revenue: {info['enterprise_to_revenue']:.2f}")
        if val_parts:
            parts.append("\nValuation: " + " | ".join(val_parts))

        # --- Price & Momentum ---
        momentum_parts = []
        if info.get("beta"):
            momentum_parts.append(f"Beta: {info['beta']:.2f}")
        if info.get("fifty_two_week_high") and info.get("fifty_two_week_low"):
            momentum_parts.append(f"52W Range: ${info['fifty_two_week_low']:.2f} - ${info['fifty_two_week_high']:.2f}")
        if info.get("fifty_day_average"):
            momentum_parts.append(f"50-Day MA: ${info['fifty_day_average']:.2f}")
        if info.get("two_hundred_day_average"):
            momentum_parts.append(f"200-Day MA: ${info['two_hundred_day_average']:.2f}")
        if momentum_parts:
            parts.append("Momentum: " + " | ".join(momentum_parts))

        # --- Profitability & Quality ---
        quality_parts = []
        if info.get("gross_margins"):
            quality_parts.append(f"Gross Margin: {info['gross_margins'] * 100:.1f}%")
        if info.get("operating_margins"):
            quality_parts.append(f"Operating Margin: {info['operating_margins'] * 100:.1f}%")
        if info.get("profit_margins"):
            quality_parts.append(f"Net Margin: {info['profit_margins'] * 100:.1f}%")
        if info.get("return_on_equity"):
            quality_parts.append(f"ROE: {info['return_on_equity'] * 100:.1f}%")
        if info.get("return_on_assets"):
            quality_parts.append(f"ROA: {info['return_on_assets'] * 100:.1f}%")
        if quality_parts:
            parts.append("\nProfitability & Quality: " + " | ".join(quality_parts))

        # --- Growth ---
        growth_parts = []
        if info.get("revenue_growth"):
            growth_parts.append(f"Revenue Growth (YoY): {info['revenue_growth'] * 100:.1f}%")
        if info.get("earnings_growth"):
            growth_parts.append(f"Earnings Growth (YoY): {info['earnings_growth'] * 100:.1f}%")
        if info.get("earnings_quarterly_growth"):
            growth_parts.append(f"Quarterly Earnings Growth: {info['earnings_quarterly_growth'] * 100:.1f}%")
        if growth_parts:
            parts.append("Growth: " + " | ".join(growth_parts))

        # --- Cash Flow & Balance Sheet ---
        cf_parts = []
        if info.get("free_cash_flow"):
            cf_parts.append(f"Free Cash Flow: ${info['free_cash_flow']:,.0f}")
        if info.get("operating_cash_flow"):
            cf_parts.append(f"Operating Cash Flow: ${info['operating_cash_flow']:,.0f}")
        if info.get("total_cash"):
            cf_parts.append(f"Cash on Hand: ${info['total_cash']:,.0f}")
        if info.get("total_debt"):
            cf_parts.append(f"Total Debt: ${info['total_debt']:,.0f}")
        if info.get("debt_to_equity"):
            cf_parts.append(f"Debt/Equity: {info['debt_to_equity']:.1f}%")
        if info.get("current_ratio"):
            cf_parts.append(f"Current Ratio: {info['current_ratio']:.2f}")
        if cf_parts:
            parts.append("\nBalance Sheet & Cash Flow: " + " | ".join(cf_parts))

        # --- Per-Share Data ---
        ps_parts = []
        if info.get("eps_trailing"):
            ps_parts.append(f"EPS (TTM): ${info['eps_trailing']:.2f}")
        if info.get("eps_forward"):
            ps_parts.append(f"EPS (Forward): ${info['eps_forward']:.2f}")
        if info.get("book_value"):
            ps_parts.append(f"Book Value/Share: ${info['book_value']:.2f}")
        if info.get("revenue_per_share"):
            ps_parts.append(f"Revenue/Share: ${info['revenue_per_share']:.2f}")
        if ps_parts:
            parts.append("Per-Share: " + " | ".join(ps_parts))

        # --- Dividends ---
        div_parts = []
        if info.get("dividend_yield") and info["dividend_yield"] > 0:
            div_parts.append(f"Dividend Yield: {info['dividend_yield'] * 100:.2f}%")
        if info.get("dividend_rate"):
            div_parts.append(f"Annual Dividend: ${info['dividend_rate']:.2f}")
        if info.get("payout_ratio"):
            div_parts.append(f"Payout Ratio: {info['payout_ratio'] * 100:.1f}%")
        if info.get("five_year_avg_dividend_yield"):
            div_parts.append(f"5Y Avg Yield: {info['five_year_avg_dividend_yield']:.2f}%")
        if div_parts:
            parts.append("\nDividends: " + " | ".join(div_parts))

        # --- Ownership & Analyst Consensus ---
        own_parts = []
        if info.get("held_percent_insiders"):
            own_parts.append(f"Insider Ownership: {info['held_percent_insiders'] * 100:.2f}%")
        if info.get("held_percent_institutions"):
            own_parts.append(f"Institutional Ownership: {info['held_percent_institutions'] * 100:.1f}%")
        if info.get("short_ratio"):
            own_parts.append(f"Short Ratio: {info['short_ratio']:.2f}")
        if info.get("short_percent_of_float"):
            own_parts.append(f"Short % of Float: {info['short_percent_of_float'] * 100:.2f}%")
        if own_parts:
            parts.append("\nOwnership: " + " | ".join(own_parts))

        analyst_parts = []
        if info.get("analyst_recommendation"):
            analyst_parts.append(f"Consensus: {info['analyst_recommendation']}")
        if info.get("number_of_analysts"):
            analyst_parts.append(f"# of Analysts: {info['number_of_analysts']}")
        if info.get("target_mean_price"):
            analyst_parts.append(f"Mean Target: ${info['target_mean_price']:.2f}")
        if info.get("target_low_price") and info.get("target_high_price"):
            analyst_parts.append(f"Target Range: ${info['target_low_price']:.2f} - ${info['target_high_price']:.2f}")
        if analyst_parts:
            parts.append("Analyst Consensus: " + " | ".join(analyst_parts))

        # --- Forward estimates + analyst-grade momentum (FMP-enriched) ---
        fwd_parts = []
        if info.get("forward_eps_est"):
            fwd_parts.append(f"Next-FY EPS est: ${info['forward_eps_est']:.2f}")
        if info.get("forward_revenue_est"):
            fwd_parts.append(f"Next-FY Revenue est: ${info['forward_revenue_est']:,.0f}")
        if info.get("grade_trend"):
            fwd_parts.append(str(info["grade_trend"]))
        if fwd_parts:
            parts.append("Forward / Analyst momentum: " + " | ".join(fwd_parts))

        # --- Earnings History ---
        if earnings.get("quarters"):
            parts.append("\nQuarterly Earnings (last 4-8 quarters):")
            for q in earnings["quarters"][:8]:
                rev = f"${q['revenue']:,.0f}" if q.get("revenue") else "N/A"
                ni = f"${q['net_income']:,.0f}" if q.get("net_income") else "N/A"
                eps = f"${q['eps']:.2f}" if q.get("eps") else "N/A"
                parts.append(f"  {q['date']}: Revenue={rev}, Net Income={ni}, EPS={eps}")

        # --- Recent News (prefer FMP's financial news — richer + more reliable; yfinance fallback) ---
        try:
            from app.services import market_providers as mp
            fmp_articles = mp.fmp_news(ticker, 8)
        except Exception:
            fmp_articles = []
        if fmp_articles:
            parts.append("\nRecent Financial News:")
            for a in fmp_articles[:8]:
                title = (a.get("title") or "").strip()
                site, date = a.get("site") or "", (a.get("publishedDate") or "")[:10]
                if title:
                    parts.append(f"  - {title}" + (f" ({site}{', ' + date if date else ''})" if site else ""))
        elif news:
            parts.append("\nRecent News Headlines:")
            for article in news[:8]:
                title = article.get("title", "")
                publisher = article.get("publisher", "")
                if title:
                    parts.append(f"  - {title}" + (f" ({publisher})" if publisher else ""))

        # --- Annual Financial Trends (5Y) ---
        try:
            from app.services.market_data import get_annual_financials, compute_piotroski_score, get_peer_comparison

            annual_data = get_annual_financials(ticker)
            if annual_data.get("annual"):
                parts.append("\n5-Year Annual Financial Trends:")
                for yr in annual_data["annual"]:
                    line_parts = [f"  {yr['year']}:"]
                    if yr.get("revenue"):
                        line_parts.append(f"Rev=${yr['revenue']:,.0f}")
                    if yr.get("net_income"):
                        line_parts.append(f"NI=${yr['net_income']:,.0f}")
                    if yr.get("fcf"):
                        line_parts.append(f"FCF=${yr['fcf']:,.0f}")
                    if yr.get("gross_margin"):
                        line_parts.append(f"GM={yr['gross_margin'] * 100:.1f}%")
                    if yr.get("operating_margin"):
                        line_parts.append(f"OpM={yr['operating_margin'] * 100:.1f}%")
                    if yr.get("net_margin"):
                        line_parts.append(f"NM={yr['net_margin'] * 100:.1f}%")
                    if yr.get("roic"):
                        line_parts.append(f"ROIC={yr['roic'] * 100:.1f}%")
                    parts.append(" | ".join(line_parts))

                # Compute YoY growth rates
                annual = annual_data["annual"]
                if len(annual) >= 2 and annual[0].get("revenue") and annual[1].get("revenue") and annual[1]["revenue"] > 0:
                    rev_growth = ((annual[0]["revenue"] - annual[1]["revenue"]) / annual[1]["revenue"]) * 100
                    parts.append(f"  Latest YoY Revenue Growth: {rev_growth:.1f}%")
                if len(annual) >= 2 and annual[0].get("fcf") and annual[1].get("fcf") and annual[1]["fcf"] != 0:
                    fcf_growth = ((annual[0]["fcf"] - annual[1]["fcf"]) / abs(annual[1]["fcf"])) * 100
                    parts.append(f"  Latest YoY FCF Growth: {fcf_growth:.1f}%")

                # Latest ROIC and FCF Yield
                latest = annual[0]
                if latest.get("roic"):
                    parts.append(f"\nROIC (Return on Invested Capital): {latest['roic'] * 100:.1f}% — {'Excellent (>15%)' if latest['roic'] > 0.15 else 'Good (10-15%)' if latest['roic'] > 0.10 else 'Below average (<10%)'}")
                if latest.get("fcf_yield"):
                    parts.append(f"FCF Yield: {latest['fcf_yield'] * 100:.2f}% — {'Attractive (>5%)' if latest['fcf_yield'] > 0.05 else 'Fair (2-5%)' if latest['fcf_yield'] > 0.02 else 'Low (<2%)'}")

            # Piotroski F-Score
            pio = compute_piotroski_score(ticker)
            if pio.get("score") is not None:
                label = "Strong" if pio["score"] >= 7 else "Moderate" if pio["score"] >= 4 else "Weak"
                parts.append(f"\nPiotroski F-Score: {pio['score']}/9 ({label} financial health)")

            # Peer/Sector comparison
            peers = get_peer_comparison(ticker)
            if peers.get("sector_pe") and peers.get("stock_pe"):
                prem_disc = peers.get("pe_vs_sector")
                label = f"{abs(prem_disc):.0f}% {'premium' if prem_disc > 0 else 'discount'}" if prem_disc else "in line"
                parts.append(f"\nPeer Context: P/E {peers['stock_pe']:.1f}x vs {peers['sector']} sector median {peers['sector_pe']:.1f}x ({label})")

            # DCF Fair Value
            from app.services.market_data import compute_dcf
            dcf = compute_dcf(ticker)
            if dcf.get("fair_value"):
                a = dcf["assumptions"]
                parts.append(f"\nDCF Fair Value: ${dcf['fair_value']:.2f}/share (WACC={a['wacc']}%, Growth Yr1-3={a['phase1_growth']}%, Yr4-5={a['phase2_growth']}%, Terminal={a['terminal_growth']}%)")
                parts.append(f"DCF Entry Price (20% margin of safety): ${dcf['entry_price']:.2f}/share")
                if dcf.get("upside_pct") is not None:
                    parts.append(f"DCF Upside from current: {dcf['upside_pct']:+.1f}%")
        except Exception:
            logger.warning("Failed to add advanced enrichment for %s", ticker)

        # Buffer raw data for DB cache write-through
        _enrichment_buffer[ticker.upper()] = {
            "company_info": info,
            "earnings": earnings,
            "news": news,
            "market_data": {
                "current_price": current_price,
                "previous_close": prev_close,
            },
        }

        if parts:
            return "\n\nReal-time financial data (use these exact figures):\n" + "\n".join(parts) + "\n", current_price

    except Exception:
        logger.warning("Failed to enrich analysis for %s with market data", ticker)

    return "", current_price


# ── Stock Analysis ──────────────────────────────────────────────


async def analyze_stock(ticker: str, api_key: str, context: str | None = None, model: str | None = None) -> dict:
    """Generate a comprehensive long-term stock research report, enriched with real market data."""
    enrichment, current_price = _build_enrichment(ticker)

    prompt = f"""Analyze {ticker} as a potential 10-15 year investment.
{enrichment}
CRITICAL RULES:
1. Use the EXACT financial data provided above — cite specific numbers (not "strong growth" but "24.1% YoY revenue growth, accelerating from 18.3%")
2. When discussing valuation, reference the stock's P/E vs sector median AND whether margins/growth justify any premium or discount
3. For the thesis, explain WHAT drives the business in plain language a non-finance person understands — then back it with data
4. For risks, quantify: "Revenue deceleration from 24% to <10% would compress P/E from 30x to 18x → ~40% downside"

{"Additional context from the user: " + context if context else ""}

Provide your analysis as JSON with these exact keys:
{{
  "company_name": "Full company name",
  "current_price": <current stock price as number>,
  "valuation": {{
    "bear": <fair value in bear scenario — be specific about assumptions>,
    "base": <fair value in base scenario>,
    "bull": <fair value in bull scenario>,
    "methodology": "2-3 sentence methodology: DCF growth rate, discount rate, terminal multiple, OR comps-based with peer multiples. State your key assumptions clearly."
  }},
  "investment_thesis": "3-4 paragraphs. Para 1: What does this company DO and WHY is it a good business (moat, competitive advantage) — explain like talking to a smart friend who doesn't follow markets. Para 2: Growth trajectory — cite revenue growth trend, margin expansion/contraction, TAM opportunity with specific numbers. Para 3: Financial quality — ROIC, FCF generation, balance sheet strength, Piotroski score context. Para 4: Why own for 10+ years — the durable edge.",
  "bull_case": "Bull case with 5-year target price AND implied CAGR. What specific catalysts? New products, market expansion, margin improvement — with numbers. Example: 'If margins expand from 25% to 32% and revenue compounds at 18%, 5Y target is $X (Y% CAGR).'",
  "bear_case": "Bear case with downside target. Distinguish temporary dip (buy more) from permanent value destruction (sell). What SPECIFIC metric would tell you the thesis is broken? Example: 'If gross margins fall below 50% for 2 quarters, the moat is eroding.'",
  "key_risks": [
    "Risk 1 — Probability: High/Medium/Low | Severity: Critical/Moderate/Minor | Impact: estimated % downside if this materializes",
    "Risk 2 — same format",
    "Risk 3 — same format",
    "Risk 4 — same format",
    "Risk 5 — same format"
  ],
  "quality_score": {{
    "moat": <1-10 competitive moat durability>,
    "management": <1-10 capital allocation track record>,
    "financial_health": <1-10 balance sheet, FCF quality, Piotroski context>,
    "growth_runway": <1-10 remaining TAM and growth opportunity>,
    "overall": <1-10 composite — weight moat and financial health most heavily>
  }},
  "sector_outlook": "2-3 sentences on the sector's next decade — cite specific secular trends, regulatory risks, disruption vectors",
  "sentiment_summary": "Current market positioning: analyst consensus, institutional ownership trends, short interest — bullish/bearish/neutral and WHY",
  "verdict": "BUY | HOLD | SELL — one word",
  "confidence": "HIGH | MEDIUM | LOW — based on data quality and thesis clarity",
  "entry_price": <recommended buy-below price that provides ~20% margin of safety below base fair value>,
  "risk_reward": "X:Y ratio — e.g. '2.5:1' meaning $2.50 upside for every $1 downside from current price",
  "thesis_breaks": [
    "Specific metric + threshold that would invalidate this thesis. Example: 'Gross margin < 55% for 2 consecutive quarters'",
    "Second break condition",
    "Third break condition"
  ]
}}

Return ONLY valid JSON — no markdown, no code fences."""

    raw = await _call_claude(STOCK_ANALYZER_SYSTEM, prompt, api_key, max_tokens=8192, model=model, web_search=True)

    try:
        parsed = _parse_json_robust(_strip_json_fences(raw))
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse stock analysis JSON for %s", ticker)
        parsed = _fallback_stock_response(ticker, raw)

    # Ensure all required fields have defaults (Claude sometimes returns truncated JSON)
    defaults = _fallback_stock_response(ticker, raw)
    for key in defaults:
        if key not in parsed:
            parsed[key] = defaults[key]

    parsed["ticker"] = ticker
    parsed["raw_analysis"] = raw
    if current_price:
        parsed["current_price"] = round(current_price, 2)

    # Attach structured financials from enrichment data for the Financials tab
    parsed["financials"] = _extract_financials(ticker)

    # Override entry_price with actual DCF computation (not Claude's guess)
    try:
        from app.services.market_data import compute_dcf
        dcf = compute_dcf(ticker)
        if dcf.get("fair_value") and dcf.get("entry_price"):
            parsed["dcf_fair_value"] = dcf["fair_value"]
            parsed["entry_price"] = dcf["entry_price"]
            parsed["dcf_assumptions"] = dcf.get("assumptions")
            parsed["dcf_upside_pct"] = dcf.get("upside_pct")
    except Exception:
        pass  # Keep Claude's estimate as fallback

    return parsed


# ── Bear Case ───────────────────────────────────────────────────


async def generate_bear_case(
    ticker: str,
    api_key: str,
    current_thesis: str | None = None,
    scenario: str | None = None,
    model: str | None = None,
) -> dict:
    """Generate the strongest possible bear case against a stock, grounded in real data."""
    enrichment, current_price = _build_enrichment(ticker)

    thesis_context = ""
    if scenario:
        thesis_context = f"CUSTOM STRESS SCENARIO to analyze: {scenario}\nFocus your entire bear case on this specific scenario."
    elif current_thesis:
        thesis_context = "Current investment thesis to stress-test:\n" + current_thesis
    else:
        thesis_context = "Generate a comprehensive bear case for a long-term holder of this stock."

    price_context = f"\nCurrent stock price: ${current_price:.2f}" if current_price else ""

    prompt = f"""Stock: {ticker}{price_context}
{enrichment}
{thesis_context}

Using the financial data above, build the strongest possible bear case for a 10-15 year holder.
Focus on risks that could PERMANENTLY impair the business, not just cause a temporary drawdown.

Provide your analysis as JSON with these exact keys:
{{
  "competitive_threats": "What could erode the moat? Disruptive competitors, technology shifts, business model obsolescence. Be specific about who/what the threat is.",
  "valuation_concerns": "Is the current valuation sustainable? What happens if multiples contract to historical lows or sector averages? Include specific downside targets with math.",
  "financial_risks": "Are margins peaking? Is FCF quality deteriorating? Debt sustainability concerns? Working capital trends? Use the financial data provided.",
  "secular_headwinds": "Industry-level structural risks: regulatory threats, demographic shifts, technological disruption, ESG/climate risks, geopolitical exposure.",
  "management_risks": "Capital allocation red flags, excessive compensation, insider selling patterns, governance concerns, key-person risk.",
  "consensus_blindspots": "The non-obvious risk that most bulls are ignoring. What's priced in vs. what could surprise to the downside?",
  "estimated_impact_pct": <estimated percentage decline as negative number, e.g. -35.0>,
  "stressed_price": <estimated stock price after bear case plays out>,
  "scenario_name": "Short name for the bear scenario (e.g. 'AI Spending Slowdown', 'Regulatory Crackdown')"
}}

Return ONLY valid JSON — no markdown, no code fences."""

    raw = await _call_claude(BEAR_CASE_SYSTEM, prompt, api_key, model=model, web_search=True)

    defaults = {
        "competitive_threats": "",
        "valuation_concerns": "",
        "financial_risks": "",
        "secular_headwinds": "",
        "management_risks": "",
        "consensus_blindspots": "",
        "estimated_impact_pct": None,
        "stressed_price": None,
        "scenario_name": "",
    }

    try:
        parsed = _parse_json_robust(_strip_json_fences(raw))
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse bear case JSON for %s", ticker)
        defaults["competitive_threats"] = raw[:500]
        parsed = defaults

    for key in defaults:
        if key not in parsed:
            parsed[key] = defaults[key]

    parsed["ticker"] = ticker
    parsed["raw_analysis"] = raw
    return parsed


# ── Thesis Generation ───────────────────────────────────────────


async def generate_thesis(ticker: str, api_key: str, context: str | None = None, model: str | None = None) -> dict:
    """Generate a structured, monitorable long-term investment thesis grounded in real data."""
    enrichment, _ = _build_enrichment(ticker)

    prompt = f"""Stock: {ticker}
{enrichment}
{"Additional context: " + context if context else ""}

Build a structured investment thesis for a 10-15 year hold. Use the real financial data above
to set specific, measurable thresholds for each key driver.

Generate the thesis as JSON with these exact keys:
{{
  "core_thesis": "1-2 sentence core thesis — why own this for 10+ years?",
  "key_drivers": [
    {{
      "metric": "Specific metric name (e.g. 'Revenue Growth Rate', 'FCF Margin', 'ROIC')",
      "current_value": "Current value from the data above",
      "threshold": "Value that would break the thesis (e.g. 'Below 8% for 2 consecutive quarters')",
      "why_it_matters": "Why this metric is critical to the long-term thesis",
      "status": "passing"
    }}
  ],
  "bull_target": "Bull case: 5-year and 10-year price targets with implied CAGR. What assumptions drive this?",
  "bear_target": "Bear case: downside target and what triggers it. At what price would you consider cutting losses?",
  "conviction_signals": ["Signal 1 that would increase conviction", "Signal 2"],
  "warning_signals": ["Signal 1 that would decrease conviction / trigger exit", "Signal 2"],
  "position_sizing": "Suggested portfolio allocation (%) given the risk/reward profile. Explain the reasoning.",
  "timeframe": "Thesis evaluation timeframe and recommended review cadence (e.g. 'Review quarterly, 10-year hold')"
}}

Include 4-5 key drivers, each tied to a specific measurable metric from the financial data.
Return ONLY valid JSON — no markdown, no code fences."""

    raw = await _call_claude(THESIS_GENERATOR_SYSTEM, prompt, api_key, model=model, web_search=True)

    defaults = {
        "core_thesis": raw[:500],
        "key_drivers": [],
        "bull_target": "",
        "bear_target": "",
        "conviction_signals": [],
        "warning_signals": [],
        "position_sizing": "",
        "timeframe": "12 months",
    }

    try:
        parsed = _parse_json_robust(_strip_json_fences(raw))
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse thesis JSON for %s", ticker)
        parsed = defaults

    for key in defaults:
        if key not in parsed:
            parsed[key] = defaults[key]

    parsed["ticker"] = ticker
    parsed["raw_analysis"] = raw
    return parsed


# ── Sentiment Analysis ──────────────────────────────────────────


async def analyze_sentiment(ticker: str, api_key: str, model: str | None = None) -> dict:
    """Generate data-backed sentiment scores from multiple dimensions."""
    enrichment, _ = _build_enrichment(ticker)

    prompt = f"""Analyze the current market sentiment for {ticker} using the real data below.
{enrichment}
Score sentiment across each dimension, grounding every score in the data provided above.
If data is insufficient for a dimension, note that and estimate conservatively.

Return JSON with these exact keys:
{{
  "scores": {{
    "news": <0-100 integer — based on the tone of recent headlines above>,
    "filings": <0-100 integer — based on earnings trends, revenue growth, margin trajectory>,
    "insider": <0-100 integer — based on insider ownership and short interest data>,
    "analyst": <0-100 integer — based on analyst consensus, target prices, and recommendation>,
    "composite": <0-100 integer — weighted blend: news 20%, filings 30%, insider 20%, analyst 30%>
  }},
  "summary": "3-4 sentence sentiment summary grounded in the specific data points. Cite the numbers."
}}

Scoring guide: 0-30 = very bearish, 30-45 = bearish, 45-55 = neutral, 55-70 = bullish, 70-100 = very bullish.
Return ONLY valid JSON — no markdown, no code fences."""

    raw = await _call_claude(SENTIMENT_SYSTEM, prompt, api_key, max_tokens=1024, model=model)

    defaults = {
        "scores": {"news": 50, "filings": 50, "insider": 50, "analyst": 50, "composite": 50},
        "summary": raw[:300],
    }

    try:
        parsed = _parse_json_robust(_strip_json_fences(raw))
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse sentiment JSON for %s", ticker)
        parsed = defaults

    for key in defaults:
        if key not in parsed:
            parsed[key] = defaults[key]

    parsed["ticker"] = ticker
    parsed["raw_analysis"] = raw
    return parsed


# ── Full Investment Report ─────────────────────────────────────


async def generate_full_report(ticker: str, api_key: str, context: str | None = None, model: str | None = None) -> dict:
    """Generate a comprehensive, publishable-quality investment report."""
    from datetime import datetime, timezone

    enrichment, current_price = _build_enrichment(ticker, fresh=True)

    prompt = f"""Write a comprehensive investment report for {ticker}.
{enrichment}
IMPORTANT: Use the financial data provided above — these are real-time figures.

{"Additional context from the user: " + context if context else ""}

Provide your report as JSON with these exact keys:
{{
  "company_name": "Full company name",
  "executive_summary": "2-3 sentence executive summary — key thesis, current valuation assessment, and recommendation.",
  "valuation_analysis": "Detailed DCF valuation analysis (3-4 paragraphs). Show assumptions: growth rate, WACC, terminal multiple. Present bear/base/bull price targets with methodology. Compare to peer valuations.",
  "investment_thesis": "Complete investment thesis (3-4 paragraphs) covering both bull and bear perspectives. Key growth drivers, competitive advantages, and what could go wrong.",
  "key_risks": [
    "Risk 1 — ranked by probability x severity with explanation",
    "Risk 2",
    "Risk 3",
    "Risk 4",
    "Risk 5"
  ],
  "catalysts": [
    "Catalyst 1 — near-term or long-term with expected timeline",
    "Catalyst 2",
    "Catalyst 3"
  ],
  "financial_highlights": "Key financial metrics and trends (2-3 paragraphs). Margins, growth rates, balance sheet strength, FCF generation, capital returns program.",
  "verdict": "Buy" or "Hold" or "Avoid",
  "confidence": "High" or "Medium" or "Low",
  "verdict_reasoning": "2-3 sentences explaining the verdict and confidence level.",
  "price_targets": {{
    "bear": <bear case price target>,
    "base": <fair value estimate>,
    "bull": <bull case price target>
  }}
}}

Return ONLY valid JSON — no markdown, no code fences."""

    raw = await _call_claude(FULL_REPORT_SYSTEM, prompt, api_key, max_tokens=16384, model=model, web_search=True)

    stripped = _strip_json_fences(raw)
    defaults = {
        "company_name": ticker,
        "executive_summary": stripped[:500],
        "valuation_analysis": "",
        "investment_thesis": "",
        "key_risks": [],
        "catalysts": [],
        "financial_highlights": "",
        "verdict": "Hold",
        "confidence": "Medium",
        "verdict_reasoning": "",
        "price_targets": {"bear": 0, "base": 0, "bull": 0},
    }

    try:
        parsed = _parse_json_robust(stripped)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse full report JSON for %s", ticker)
        parsed = defaults

    for key in defaults:
        if key not in parsed:
            parsed[key] = defaults[key]

    parsed["ticker"] = ticker
    parsed["raw_report"] = raw
    parsed["generated_at"] = datetime.now(timezone.utc).isoformat()
    if current_price:
        parsed["current_price"] = round(current_price, 2)
    return parsed


# ── Portfolio Analysis (user-triggered deep research) ──────────


async def analyze_portfolio(api_key: str, portfolio_context: str | None = None, model: str | None = None) -> dict:
    """Deep portfolio analysis with fresh data for every held stock.
    User-triggered — fetches live fundamentals, earnings, news, and risk data
    for each position before sending to Claude for comprehensive analysis.
    """
    from app.services import robinhood

    if not robinhood.is_connected():
        return {
            "summary": "Connect your Robinhood account to run a portfolio analysis.",
            "alerts": [],
            "market_context": "",
            "stock_analyses": [],
            "raw_brief": "",
        }

    # Clear robinhood cache to get fresh position data
    robinhood.clear_cache()
    positions = robinhood.get_positions()
    summary = robinhood.get_portfolio_summary()

    if not positions or not summary:
        return {
            "summary": "Unable to fetch portfolio data. Please try again later.",
            "alerts": [],
            "market_context": "",
            "stock_analyses": [],
            "raw_brief": "",
        }

    # ── Build per-position data with P&L ──
    position_lines = []
    total_cost = 0.0
    for p in positions:
        cost_basis = p["shares"] * p["avg_cost"]
        unrealized_pnl = p["equity"] - cost_basis
        pnl_pct = (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0
        total_cost += cost_basis
        position_lines.append(
            f"  {p['symbol']}: {p['shares']} shares @ ${p['avg_cost']:.2f} avg | "
            f"Now ${p['current_price']:.2f} | "
            f"P&L: {'+'if unrealized_pnl >= 0 else ''}${unrealized_pnl:,.2f} ({'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%) | "
            f"Sector: {p.get('sector', 'Unknown')} | "
            f"Weight: {(p['equity'] / summary['total_value'] * 100):.1f}%"
        )

    # ── Sector allocation ──
    sector_map: dict[str, float] = {}
    for p in positions:
        sector = p.get("sector", "Unknown") or "Unknown"
        sector_map[sector] = sector_map.get(sector, 0) + p.get("equity", 0)
    sector_lines = []
    for sector, val in sorted(sector_map.items(), key=lambda x: -x[1]):
        pct = val / summary["total_value"] * 100 if summary["total_value"] else 0
        sector_lines.append(f"  {sector}: ${val:,.2f} ({pct:.1f}%)")

    # ── Risk metrics ──
    risk_context = ""
    try:
        from app.services.risk import compute_risk_metrics
        risk = compute_risk_metrics(positions)
        if risk.get("source") != "default":
            risk_context = f"""
Risk Metrics:
  Risk Score: {risk['score']}/100
  Portfolio Volatility: {risk['portfolio_volatility']:.1f}% annualized
  Max Drawdown (90d): {risk['max_drawdown']:.1f}%
  Daily VaR (95%): {risk['daily_var_95']:.2f}%
  Monthly CVaR (95%): {risk['monthly_cvar_95']:.2f}%"""
            if risk.get("concentration"):
                risk_context += f"\n  Concentration (HHI): {risk['concentration']['hhi']:.4f} | Top 5 sectors: {risk['concentration']['top5_pct']:.1f}%"
            if risk.get("correlation_alerts"):
                for a in risk["correlation_alerts"][:5]:
                    risk_context += f"\n  Correlated pair: {a['pair'][0]}/{a['pair'][1]} ({a['correlation']:.2f})"
            if risk.get("stress_tests"):
                risk_context += "\n  Stress test impacts:"
                for st in risk["stress_tests"]:
                    risk_context += f"\n    {st['scenario']}: {st['impact']:.1f}%"
    except Exception:
        pass

    # ── Fetch FRESH fundamental data for each position (the deep research part) ──
    stock_data_blocks = []
    symbols = [p["symbol"] for p in positions[:15]]  # Top 15 by equity
    logger.info("Portfolio analysis: fetching fresh data for %d positions", len(symbols))

    for symbol in symbols:
        enrichment_text, _ = _build_enrichment(symbol, fresh=True)
        if enrichment_text:
            stock_data_blocks.append(f"\n{'='*60}\n{symbol} — FUNDAMENTAL DATA\n{'='*60}{enrichment_text}")

    stock_research = "\n".join(stock_data_blocks) if stock_data_blocks else "\n(No fundamental data available)"

    prompt = f"""Perform a deep portfolio analysis for a long-term buy-and-hold investor (10-15 year horizon).
I'm providing you with FRESH, REAL-TIME data for every position — use these exact figures.

{'='*60}
PORTFOLIO OVERVIEW
{'='*60}
  Total Value: ${summary['total_value']:,.2f}
  Total Cost Basis: ${total_cost:,.2f}
  Daily Change: {'+' if summary['daily_change'] >= 0 else ''}${summary['daily_change']:,.2f} ({'+' if summary['daily_change_pct'] >= 0 else ''}{summary['daily_change_pct']}%)
  Total Return: {'+' if summary['total_gain'] >= 0 else ''}${summary['total_gain']:,.2f} ({'+' if summary['total_gain_pct'] >= 0 else ''}{summary['total_gain_pct']}%)
  Buying Power: ${summary.get('buying_power', 0):,.2f}

Holdings (with cost basis and P&L):
{chr(10).join(position_lines)}

Sector Allocation:
{chr(10).join(sector_lines)}
{risk_context}

{'='*60}
PER-STOCK FUNDAMENTAL RESEARCH (LIVE DATA)
{'='*60}
{stock_research}

{"Additional context from the user: " + portfolio_context if portfolio_context else ""}

{'='*60}
ANALYSIS INSTRUCTIONS
{'='*60}
This is a DEEP analysis — take your time and be thorough. The user triggered this manually.

Analyze each stock through the lens of a 10-15 year holder. For each position, evaluate:
- Is the current thesis still intact? What would break it?
- Is the valuation reasonable for a long-term hold? Overextended?
- How is the company's financial health (margins, FCF, debt)?
- What are the growth prospects for the next decade?
- Should the position be sized up, held, trimmed, or sold?

Then evaluate the PORTFOLIO as a whole:
- Sector concentration risk — is it too tech-heavy? Too correlated?
- Which positions are the strongest long-term holds?
- Which positions are the weakest and need attention?
- Tax-loss harvesting opportunities (positions with significant losses)
- Rebalancing needs — any position too large or too small?
- What's missing? Gaps in sector exposure, defensive positions, dividend income?

Return JSON with these exact keys:
{{
  "summary": "2-3 sentence executive summary of portfolio health and the most important finding",
  "alerts": [
    {{
      "type": "rebalance | tax_harvest | thesis_break | risk | opportunity | overvalued | undervalued",
      "severity": "info | warning | critical",
      "title": "Concise alert title",
      "description": "Detailed explanation grounded in the financial data. Cite specific numbers (P/E, growth rate, margin trend, etc.)",
      "action": "Specific, actionable recommendation with numbers (e.g. 'Trim AAPL from 25% to 15% of portfolio — P/E of 34x is 40% above 5Y avg')"
    }}
  ],
  "stock_analyses": [
    {{
      "symbol": "TICKER",
      "verdict": "strong_hold | hold | watch | trim | sell",
      "quality_score": <1-10 overall quality>,
      "thesis": "1-2 sentence investment thesis for THIS position",
      "concerns": "Key risk or concern for this specific stock",
      "action": "Recommended action (hold, trim to X%, add more, etc.)"
    }}
  ],
  "market_context": "3-4 sentence macro outlook relevant to this portfolio's sector exposure. Include interest rate environment, economic cycle position, and sector rotation trends."
}}

Generate 5-10 alerts ranked by importance. Be specific — cite the data.
Include a stock_analyses entry for EVERY position in the portfolio.
Return ONLY valid JSON — no markdown, no code fences."""

    raw = await _call_claude(DAILY_BRIEF_SYSTEM, prompt, api_key, max_tokens=8192, model=model)

    try:
        parsed = json.loads(_strip_json_fences(raw))
    except json.JSONDecodeError:
        logger.warning("Failed to parse portfolio analysis JSON")
        parsed = {
            "summary": raw[:500],
            "alerts": [],
            "stock_analyses": [],
            "market_context": "",
        }

    parsed["raw_brief"] = raw
    return parsed


async def stream_portfolio_analysis(
    api_key: str, portfolio_context: str | None = None, model: str | None = None
) -> AsyncIterator[str]:
    """Stream portfolio analysis as SSE events.
    Yields JSON-encoded SSE `data:` lines for the frontend to consume.
    Event types: status (progress updates), delta (token chunks), done (final parsed JSON), error.

    IMPORTANT: All sync I/O (robinhood, yfinance, market_data) is run via
    asyncio.to_thread() so the event loop stays free to flush SSE events.
    """
    import asyncio
    import time

    def sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    yield sse("status", {"message": "Connecting to portfolio..."})

    from app.services import robinhood

    if not robinhood.is_connected():
        yield sse("error", {"message": "Connect your Robinhood account first."})
        return

    yield sse("status", {"message": "Fetching fresh portfolio data..."})

    # Run sync Robinhood calls off the event loop
    await asyncio.to_thread(robinhood.clear_cache)
    positions = await asyncio.to_thread(robinhood.get_positions)
    summary = await asyncio.to_thread(robinhood.get_portfolio_summary)

    if not positions or not summary:
        yield sse("error", {"message": "Unable to fetch portfolio data. Please try again later."})
        return

    yield sse("status", {"message": f"Got {len(positions)} positions. Building context..."})

    # ── Build the same context as analyze_portfolio ──
    position_lines = []
    total_cost = 0.0
    for p in positions:
        cost_basis = p["shares"] * p["avg_cost"]
        unrealized_pnl = p["equity"] - cost_basis
        pnl_pct = (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0
        total_cost += cost_basis
        position_lines.append(
            f"  {p['symbol']}: {p['shares']} shares @ ${p['avg_cost']:.2f} avg | "
            f"Now ${p['current_price']:.2f} | "
            f"P&L: {'+'if unrealized_pnl >= 0 else ''}${unrealized_pnl:,.2f} ({'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%) | "
            f"Sector: {p.get('sector', 'Unknown')} | "
            f"Weight: {(p['equity'] / summary['total_value'] * 100):.1f}%"
        )

    sector_map: dict[str, float] = {}
    for p in positions:
        sector = p.get("sector", "Unknown") or "Unknown"
        sector_map[sector] = sector_map.get(sector, 0) + p.get("equity", 0)
    sector_lines = []
    for sector, val in sorted(sector_map.items(), key=lambda x: -x[1]):
        pct = val / summary["total_value"] * 100 if summary["total_value"] else 0
        sector_lines.append(f"  {sector}: ${val:,.2f} ({pct:.1f}%)")

    risk_context = ""
    try:
        from app.services.risk import compute_risk_metrics
        risk = await asyncio.to_thread(compute_risk_metrics, positions)
        if risk.get("source") != "default":
            risk_context = f"""
Risk Metrics:
  Risk Score: {risk['score']}/100
  Portfolio Volatility: {risk['portfolio_volatility']:.1f}% annualized
  Max Drawdown (90d): {risk['max_drawdown']:.1f}%
  Daily VaR (95%): {risk['daily_var_95']:.2f}%
  Monthly CVaR (95%): {risk['monthly_cvar_95']:.2f}%"""
            if risk.get("concentration"):
                risk_context += f"\n  Concentration (HHI): {risk['concentration']['hhi']:.4f} | Top 5 sectors: {risk['concentration']['top5_pct']:.1f}%"
            if risk.get("correlation_alerts"):
                for a in risk["correlation_alerts"][:5]:
                    risk_context += f"\n  Correlated pair: {a['pair'][0]}/{a['pair'][1]} ({a['correlation']:.2f})"
            if risk.get("stress_tests"):
                risk_context += "\n  Stress test impacts:"
                for st in risk["stress_tests"]:
                    risk_context += f"\n    {st['scenario']}: {st['impact']:.1f}%"
    except Exception:
        pass

    symbols = [p["symbol"] for p in positions[:15]]
    yield sse("status", {"message": f"Researching {len(symbols)} stocks — fetching fundamentals, earnings, news..."})

    stock_data_blocks = []
    for i, symbol in enumerate(symbols):
        yield sse("status", {"message": f"Researching {symbol} ({i + 1}/{len(symbols)})..."})
        # Run sync yfinance/market_data calls off the event loop
        enrichment_text, _ = await asyncio.to_thread(_build_enrichment, symbol, True)
        if enrichment_text:
            stock_data_blocks.append(f"\n{'='*60}\n{symbol} — FUNDAMENTAL DATA\n{'='*60}{enrichment_text}")

    stock_research = "\n".join(stock_data_blocks) if stock_data_blocks else "\n(No fundamental data available)"

    yield sse("status", {"message": "All data gathered. Sending to Claude for deep analysis..."})

    prompt = f"""Perform a deep portfolio analysis for a long-term buy-and-hold investor (10-15 year horizon).
I'm providing you with FRESH, REAL-TIME data for every position — use these exact figures.

{'='*60}
PORTFOLIO OVERVIEW
{'='*60}
  Total Value: ${summary['total_value']:,.2f}
  Total Cost Basis: ${total_cost:,.2f}
  Daily Change: {'+' if summary['daily_change'] >= 0 else ''}${summary['daily_change']:,.2f} ({'+' if summary['daily_change_pct'] >= 0 else ''}{summary['daily_change_pct']}%)
  Total Return: {'+' if summary['total_gain'] >= 0 else ''}${summary['total_gain']:,.2f} ({'+' if summary['total_gain_pct'] >= 0 else ''}{summary['total_gain_pct']}%)
  Buying Power: ${summary.get('buying_power', 0):,.2f}

Holdings (with cost basis and P&L):
{chr(10).join(position_lines)}

Sector Allocation:
{chr(10).join(sector_lines)}
{risk_context}

{'='*60}
PER-STOCK FUNDAMENTAL RESEARCH (LIVE DATA)
{'='*60}
{stock_research}

{"Additional context from the user: " + portfolio_context if portfolio_context else ""}

{'='*60}
ANALYSIS INSTRUCTIONS
{'='*60}
This is a DEEP analysis — take your time and be thorough. The user triggered this manually.

Analyze each stock through the lens of a 10-15 year holder. For each position, evaluate:
- Is the current thesis still intact? What would break it?
- Is the valuation reasonable for a long-term hold? Overextended?
- How is the company's financial health (margins, FCF, debt)?
- What are the growth prospects for the next decade?
- Should the position be sized up, held, trimmed, or sold?

Then evaluate the PORTFOLIO as a whole:
- Sector concentration risk — is it too tech-heavy? Too correlated?
- Which positions are the strongest long-term holds?
- Which positions are the weakest and need attention?
- Tax-loss harvesting opportunities (positions with significant losses)
- Rebalancing needs — any position too large or too small?
- What's missing? Gaps in sector exposure, defensive positions, dividend income?

Return JSON with these exact keys:
{{
  "summary": "2-3 sentence executive summary of portfolio health and the most important finding",
  "alerts": [
    {{
      "type": "rebalance | tax_harvest | thesis_break | risk | opportunity | overvalued | undervalued",
      "severity": "info | warning | critical",
      "title": "Concise alert title",
      "description": "Detailed explanation grounded in the financial data. Cite specific numbers (P/E, growth rate, margin trend, etc.)",
      "action": "Specific, actionable recommendation with numbers (e.g. 'Trim AAPL from 25% to 15% of portfolio — P/E of 34x is 40% above 5Y avg')"
    }}
  ],
  "stock_analyses": [
    {{
      "symbol": "TICKER",
      "verdict": "strong_hold | hold | watch | trim | sell",
      "quality_score": <1-10 overall quality>,
      "thesis": "1-2 sentence investment thesis for THIS position",
      "concerns": "Key risk or concern for this specific stock",
      "action": "Recommended action (hold, trim to X%, add more, etc.)"
    }}
  ],
  "market_context": "3-4 sentence macro outlook relevant to this portfolio's sector exposure. Include interest rate environment, economic cycle position, and sector rotation trends."
}}

Generate 5-10 alerts ranked by importance. Be specific — cite the data.
Include a stock_analyses entry for EVERY position in the portfolio.
Return ONLY valid JSON — no markdown, no code fences."""

    # Stream Claude's response token by token
    full_text = ""
    delta_count = 0
    t0 = time.time()
    try:
        async for delta in _stream_claude(DAILY_BRIEF_SYSTEM, prompt, api_key, max_tokens=16384, model=model):
            full_text += delta
            delta_count += 1
            yield sse("delta", {"text": delta})
            if delta_count % 100 == 0:
                logger.info("Stream progress: %d deltas, %d chars, %.1fs elapsed",
                            delta_count, len(full_text), time.time() - t0)
    except Exception as e:
        logger.exception("Streaming portfolio analysis failed after %d deltas", delta_count)
        yield sse("error", {"message": f"AI analysis failed: {e}"})
        return

    elapsed = round(time.time() - t0, 1)
    logger.info("Stream complete: %d deltas, %d chars in %.1fs", delta_count, len(full_text), elapsed)

    # Parse the final result
    try:
        parsed = json.loads(_strip_json_fences(full_text))
        logger.info("Stream JSON parsed successfully")
    except json.JSONDecodeError:
        logger.warning("Failed to parse streamed portfolio analysis JSON (%d chars)", len(full_text))
        # Log the last 200 chars to see where it cut off
        logger.warning("JSON tail: ...%s", full_text[-200:])
        parsed = {
            "summary": full_text[:500],
            "alerts": [],
            "stock_analyses": [],
            "market_context": "",
        }

    # Don't include raw_brief in the done event to keep payload small
    # The frontend doesn't use raw_brief for rendering
    parsed.pop("raw_brief", None)
    done_payload = json.dumps({"result": parsed, "elapsed_seconds": elapsed})
    logger.info("Sending done event: %d bytes", len(done_payload))
    yield f"event: done\ndata: {done_payload}\n\n"


# ── Conversational Portfolio Advisor ───────────────────────────


# ── Advisor Tools ───────────────────────────────────────────────

ADVISOR_TOOLS = [
    {
        "name": "get_stock_data",
        "description": (
            "Fetch comprehensive fundamentals for any stock ticker: current price, P/E, margins, "
            "growth rates, FCF, debt, analyst targets, last 8 quarters of earnings, and recent news headlines. "
            "Use this whenever the user asks about a specific stock (owned or not) to get real, current data "
            "rather than relying on training knowledge. Returns all data as a single formatted text block."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol, e.g. 'AVAV', 'NVDA', 'TSLA'",
                }
            },
            "required": ["ticker"],
        },
    },
    # Anthropic's server-side web search tool — Claude executes internally
    {
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 3,
    },
]


def _tool_get_stock_data(ticker: str) -> str:
    """Tool handler: fetch comprehensive stock data via _build_enrichment."""
    try:
        enrichment, price = _build_enrichment(ticker.upper().strip())
        if not enrichment or "no data" in enrichment.lower():
            return f"No data available for {ticker}. It may be an invalid ticker or delisted."
        return f"Ticker: {ticker.upper()}\n{enrichment}"
    except Exception as e:
        return f"Error fetching {ticker}: {e}"


async def _stream_claude_with_tools(
    system: str,
    messages: list[dict],
    api_key: str,
    tools: list[dict],
    tool_handlers: dict,
    max_tokens: int = 8192,
    model: str | None = None,
    max_turns: int = 6,
    cache: bool = False,
) -> AsyncIterator[tuple[str, dict]]:
    """Agentic streaming loop. Yields events:
    ('delta', {'text': str})            — streaming text chunks
    ('tool_call', {'name', 'input'})    — Claude invoked a tool
    ('tool_result', {'name', 'status'}) — tool finished (status='ok'|'error')
    ('done', {})                        — conversation turn complete

    When `cache` is set, the (large, per-session-stable) system prompt and the
    tool definitions are marked with `cache_control: ephemeral` so follow-up turns
    in the same session reuse the cached prefix (Anthropic prompt caching, 5-min
    TTL refreshed each turn).
    """
    import asyncio

    client = _get_client(api_key)
    conv = list(messages)

    # Prompt caching: cache the system prompt (holds the portfolio context) and
    # the static tool defs. Both are constant within a session.
    system_param: object = system
    tools_param = tools
    extra: dict = {}
    if cache:
        system_param = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        if tools:
            tools_param = [*tools[:-1], {**tools[-1], "cache_control": {"type": "ephemeral"}}]
        # Also cache the conversation-history prefix by marking the latest message.
        # The tool loop re-calls the API up to `max_turns` times per user turn, and
        # each follow-up turn resends the whole history — this makes both reuse the
        # cached prefix instead of reprocessing it.
        if conv:
            last = conv[-1]
            content = last.get("content")
            if isinstance(content, str):
                marked = [{"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}]
            elif isinstance(content, list) and content:
                marked = [*content[:-1], {**content[-1], "cache_control": {"type": "ephemeral"}}]
            else:
                marked = content
            conv = [*conv[:-1], {**last, "content": marked}]
        # This SDK (0.42) still gates prompt caching behind the beta header.
        extra["extra_headers"] = {"anthropic-beta": "prompt-caching-2024-07-31"}

    for _ in range(max_turns):
        async with client.messages.stream(
            model=model or settings.claude_model,
            max_tokens=max_tokens,
            system=system_param,
            messages=conv,
            tools=tools_param,
            **extra,
        ) as stream:
            async for text in stream.text_stream:
                yield ("delta", {"text": text})
            final = await stream.get_final_message()

        stop_reason = final.stop_reason

        # Extract assistant content blocks
        assistant_blocks = []
        tool_uses = []
        for block in final.content:
            # Serialize the block for the next turn
            if block.type == "text":
                assistant_blocks.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                assistant_blocks.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
                tool_uses.append(block)
            # Server tool calls (e.g. web_search) are handled by Anthropic and
            # appear as separate block types; keep them in the assistant turn.
            else:
                try:
                    assistant_blocks.append(block.model_dump(mode="json"))
                except Exception:
                    pass

        if stop_reason != "tool_use" or not tool_uses:
            # Either end_turn / stop_sequence / no custom tools to execute
            yield ("done", {})
            return

        # Append assistant turn
        conv.append({"role": "assistant", "content": assistant_blocks})

        # Execute each custom tool call and build tool_result blocks
        tool_result_blocks = []
        for tu in tool_uses:
            yield ("tool_call", {"name": tu.name, "input": tu.input})
            handler = tool_handlers.get(tu.name)
            if not handler:
                tool_result_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": f"Tool '{tu.name}' not available.",
                    "is_error": True,
                })
                yield ("tool_result", {"name": tu.name, "status": "error"})
                continue
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(**tu.input)
                else:
                    result = await asyncio.to_thread(handler, **tu.input)
                tool_result_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": str(result)[:20000],  # cap to 20k chars
                })
                yield ("tool_result", {"name": tu.name, "status": "ok"})
            except Exception as e:
                tool_result_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": f"Error: {e}",
                    "is_error": True,
                })
                yield ("tool_result", {"name": tu.name, "status": "error"})

        # Append tool results as a user turn and loop
        conv.append({"role": "user", "content": tool_result_blocks})

    # Exceeded max turns
    yield ("done", {})


async def stream_advisor_chat(
    messages: list[dict],
    api_key: str,
    portfolio_context: str | None = None,
    document_context: str | None = None,
    model: str | None = None,
    token: str | None = None,
    account: str | None = None,
) -> AsyncIterator[str]:
    """Stream a conversational advisor response as SSE events.

    If portfolio_context is not provided (first message in a conversation),
    fetches live portfolio data and yields it as a 'context' event so the
    frontend can cache it for subsequent messages.

    Events: status, context, delta, done, error.
    """
    import asyncio
    import time

    def sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    t0 = time.time()

    # ── Build portfolio context (first message only) ──
    # Uses the agentic MCP for the SELECTED account (multi-account aware).
    if not portfolio_context:
        yield sse("status", {"message": "Loading your portfolio..."})

        from datetime import datetime, timedelta, timezone
        from app.services import robinhood_portfolio as rp
        from app.services.risk import compute_risk_metrics, _get_cached

        if not token:
            yield sse("error", {"message": "Connect your Robinhood account first (Settings > Robinhood)."})
            return

        try:
            acct = await rp.resolve_account_number(token, account)
            positions = await rp.get_positions(token, acct)
            summary = await rp.get_summary(token, acct)
        except Exception:
            logger.exception("Advisor portfolio fetch failed")
            yield sse("error", {"message": "Unable to fetch portfolio data. Please try again."})
            return

        if not positions or not summary:
            yield sse("error", {"message": "No holdings found for this account, or unable to fetch data."})
            return

        yield sse("status", {"message": f"Got {len(positions)} positions. Building context..."})

        total_value = summary.get("total_value", 0) or 0
        total_gain = sum(p["equity"] - p["shares"] * p["avg_cost"] for p in positions)
        total_cost = sum(p["shares"] * p["avg_cost"] for p in positions)
        total_gain_pct = (total_gain / total_cost * 100) if total_cost else 0
        daily_change = sum(p.get("equity_change", 0) for p in positions)

        lines = [
            f"Account: {acct}",
            f"Portfolio Value: ${total_value:,.2f}",
            f"Today's Change: {'+' if daily_change >= 0 else ''}${daily_change:,.2f}",
            f"Total Return (since purchase): {'+' if total_gain >= 0 else ''}${total_gain:,.2f} "
            f"({'+' if total_gain_pct >= 0 else ''}{total_gain_pct:.1f}%)",
            f"Buying Power: ${summary.get('buying_power', 0):,.2f}",
            "",
            "Holdings:",
        ]
        for p in sorted(positions, key=lambda x: -x.get("equity", 0)):
            cost_basis = p["shares"] * p["avg_cost"]
            unrealized_pnl = p["equity"] - cost_basis
            pnl_pct = (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0
            weight = p["equity"] / total_value * 100 if total_value else 0
            lines.append(
                f"  {p['symbol']}: {p['shares']:.4g} sh @ ${p['avg_cost']:.2f} avg | "
                f"Now ${p['current_price']:.2f} | "
                f"P&L: {'+' if unrealized_pnl >= 0 else ''}${unrealized_pnl:,.2f} "
                f"({'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%) | Weight: {weight:.1f}%"
            )

        # Real sector allocation + risk — reuse the cached risk compute (warmed by
        # the dashboard) when available; else compute it once here (also caches it).
        risk = _get_cached(f"risk:{acct}")
        if risk is None:
            try:
                yield sse("status", {"message": "Computing risk metrics..."})
                top = sorted(positions, key=lambda p: p.get("equity", 0), reverse=True)[:25]
                start = (datetime.now(timezone.utc) - timedelta(days=100)).strftime("%Y-%m-%dT%H:%M:%SZ")
                hist = await rp.fetch_historicals(token, [p["symbol"] for p in top] + ["SPY"], "day", start)
                risk = await asyncio.to_thread(compute_risk_metrics, positions, hist, f"risk:{acct}")
            except Exception:
                risk = None

        if risk:
            sw = risk.get("sector_weights", [])
            if sw:
                lines.append("")
                lines.append("Sector Allocation:")
                for s in sw:
                    val = s.get("value", 0)
                    pct = val / total_value * 100 if total_value else s.get("weight", 0)
                    lines.append(f"  {s['sector']}: ${val:,.2f} ({pct:.1f}%)")
            lines.append("")
            lines.append("Risk Metrics:")
            lines.append(f"  Risk Score: {risk.get('score', 0)}/100")
            lines.append(f"  Volatility: {risk.get('portfolio_volatility', 0):.1f}% annualized")
            lines.append(f"  Max Drawdown (90d): {risk.get('max_drawdown', 0):.1f}%")
            lines.append(f"  Daily VaR (95%): {risk.get('daily_var_95', 0):.2f}%")
            conc = risk.get("concentration") or {}
            if conc:
                lines.append(f"  Concentration (HHI): {conc.get('hhi', 0):.4f} | Top 5: {conc.get('top5_pct', 0):.1f}%")

        portfolio_context = "\n".join(lines)
        yield sse("context", {"portfolio_context": portfolio_context})

    yield sse("status", {"message": "Thinking..."})

    # ── Build system prompt with portfolio data + optional documents ──
    system_prompt = ADVISOR_SYSTEM.format(portfolio_context=portfolio_context)
    if document_context:
        system_prompt += (
            "\n\n---\n\n"
            "The user has uploaded research documents for reference. "
            "Use this information to inform your analysis and advice:\n\n"
            f"{document_context}"
        )

    # Append tool usage guidance to system prompt
    system_prompt += (
        "\n\n---\n\n"
        "You have access to tools for real-time data:\n"
        "  • `get_stock_data(ticker)` — fetch current fundamentals, margins, growth, earnings history, "
        "analyst targets, and recent news for ANY stock (owned or not). Use this whenever the user "
        "mentions a specific ticker. Don't rely on training knowledge for prices or current metrics.\n"
        "  • `web_search(query)` — search the web for recent news, analyst commentary, or events not in the data.\n\n"
        "Be proactive: if the user asks 'is AVAV a good buy?', immediately call `get_stock_data('AVAV')` "
        "to get real data before answering. Cite specific numbers from the tool results in your response."
    )

    # ── Stream Claude response with tool use ──
    tool_handlers = {
        "get_stock_data": _tool_get_stock_data,
    }

    full_text = ""
    delta_count = 0
    tools_invoked = 0
    try:
        async for ev_type, ev_data in _stream_claude_with_tools(
            system=system_prompt,
            messages=messages,
            api_key=api_key,
            tools=ADVISOR_TOOLS,
            tool_handlers=tool_handlers,
            max_tokens=8192,
            model=model,
            cache=True,  # per-session prompt caching (system + portfolio context + tools)
        ):
            if ev_type == "delta":
                full_text += ev_data["text"]
                delta_count += 1
                yield sse("delta", ev_data)
            elif ev_type == "tool_call":
                tools_invoked += 1
                yield sse("tool_call", ev_data)
            elif ev_type == "tool_result":
                yield sse("tool_result", ev_data)
            elif ev_type == "done":
                break
    except Exception as e:
        logger.exception("Advisor chat streaming failed after %d deltas", delta_count)
        yield sse("error", {"message": f"AI response failed: {e}"})
        return

    elapsed = round(time.time() - t0, 1)
    logger.info(
        "Advisor chat complete: %d deltas, %d tools, %d chars in %.1fs",
        delta_count, tools_invoked, len(full_text), elapsed,
    )
    yield sse("done", {"text": full_text, "elapsed_seconds": elapsed, "tools_used": tools_invoked})


# ── Helpers ─────────────────────────────────────────────────────


def _parse_json_robust(text: str) -> dict:
    """Parse JSON that may have a prematurely-closed outer object or be truncated.

    Claude sometimes generates long JSON with premature closing braces after
    large text fields (investment_thesis, bull_case, etc.), splitting the
    intended single object into multiple fragments.  This parser iteratively
    extracts and merges all fragments so no fields are lost.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to repair truncated JSON by closing open brackets/braces
    repaired = _repair_truncated_json(text)
    if repaired:
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

    # Try reassembling: remove premature outer-object closes.
    # Pattern: `"...(value)"\n}\n,\n  "next_key"` — the `}\n,` is a premature close.
    # Strategy: wrap everything between the first `{` and last `}` into a single object,
    # removing intermediate `}\n,` or `},` that split the top-level object.
    reassembled = _reassemble_split_json(text)
    if reassembled:
        try:
            return json.loads(reassembled)
        except json.JSONDecodeError:
            pass

    # Fall back to iterative raw_decode merging
    decoder = json.JSONDecoder()
    merged: dict = {}
    remaining = text

    for _ in range(20):  # safety limit
        remaining = remaining.strip().lstrip(",").strip()
        if not remaining:
            break

        # Try to decode a complete JSON object
        try:
            obj, idx = decoder.raw_decode(remaining)
            if isinstance(obj, dict):
                merged.update(obj)
            remaining = remaining[idx:].strip()
            continue
        except json.JSONDecodeError:
            pass

        # Remaining may be bare key-value pairs after a premature `}`
        # Wrap in braces and try parsing via raw_decode
        wrapped = "{" + remaining + "}"
        try:
            obj, idx = decoder.raw_decode(wrapped)
            if isinstance(obj, dict):
                merged.update(obj)
            # Calculate consumed chars from original remaining (subtract the "{")
            consumed = idx - 1
            remaining = remaining[consumed:].strip()
            continue
        except json.JSONDecodeError:
            pass

        # Try repair on the wrapped version
        repaired_wrapped = _repair_truncated_json(wrapped)
        if repaired_wrapped:
            try:
                obj = json.loads(repaired_wrapped)
                if isinstance(obj, dict):
                    merged.update(obj)
                break
            except json.JSONDecodeError:
                pass

        break

    if not merged:
        raise ValueError("Cannot parse JSON from response")

    return merged


def _reassemble_split_json(text: str) -> str | None:
    """Reassemble JSON split by premature top-level closing braces.

    Claude sometimes emits `}` after a long string value, prematurely closing
    the outer object.  This function strips those spurious closes by tracking
    brace depth (ignoring string interiors) and removing `}` tokens that
    would close the outermost object before the real end.
    """
    text = text.strip()
    if not text.startswith("{"):
        return None

    # Walk through text, tracking brace/bracket depth (skip string interiors)
    result: list[str] = []
    depth = 0
    i = 0
    length = len(text)

    while i < length:
        ch = text[i]

        if ch == '"':
            # Consume entire string (handle escapes)
            result.append(ch)
            i += 1
            while i < length:
                sc = text[i]
                result.append(sc)
                if sc == '\\':
                    i += 1
                    if i < length:
                        result.append(text[i])
                elif sc == '"':
                    break
                i += 1
            i += 1
            continue

        if ch == '{':
            depth += 1
            result.append(ch)
        elif ch == '[':
            depth += 1
            result.append(ch)
        elif ch == ']':
            depth -= 1
            result.append(ch)
        elif ch == '}':
            depth -= 1
            if depth == 0:
                # This closes the outermost object — check if there's more content
                rest = text[i + 1:].strip().lstrip(",").strip()
                if rest and rest[0] == '"':
                    # More keys follow — this was a premature close; replace with comma
                    result.append(",")
                    # Skip the `}` and any `,` / whitespace before the next key
                    i += 1
                    while i < length and text[i] in " \t\r\n,":
                        i += 1
                    depth = 1  # Re-open the outer object
                    continue
                else:
                    # Genuine close (end of object)
                    result.append(ch)
            else:
                result.append(ch)
        else:
            result.append(ch)

        i += 1

    assembled = "".join(result)

    # If depth != 0, try to close remaining open structures
    if depth > 0:
        assembled = assembled.rstrip().rstrip(",")
        assembled += "}" * depth
    elif depth < 0:
        return None  # More closes than opens — can't fix

    return assembled


def _repair_truncated_json(text: str) -> str | None:
    """Attempt to repair truncated JSON by closing open structures."""
    text = text.rstrip()

    # Track open brackets/braces (ignore those inside strings)
    stack: list[str] = []
    in_string = False
    escape = False

    for ch in text:
        if escape:
            escape = False
            continue
        if ch == '\\' and in_string:
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in ('{', '['):
            stack.append(ch)
        elif ch == '}' and stack and stack[-1] == '{':
            stack.pop()
        elif ch == ']' and stack and stack[-1] == '[':
            stack.pop()

    if not stack:
        return None  # Already balanced or not JSON

    # If we're mid-string, close it first
    if in_string:
        text += '"'

    # Strip trailing comma or colon that would be invalid before closing
    text = text.rstrip()
    if text.endswith(',') or text.endswith(':'):
        text = text[:-1]

    # Close open structures in reverse order
    for bracket in reversed(stack):
        text += '}' if bracket == '{' else ']'

    return text


def _strip_json_fences(text: str) -> str:
    """Isolate the JSON object from Claude's reply — strip markdown fences AND any prose
    that surrounds it (web_search preambles like 'Let me look up…' or trailing section
    headers), so a JSON caller gets a clean object to parse."""
    import re

    text = text.strip()
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", text)
    if match:
        return match.group(1)
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    # If there's leading/trailing prose, keep only the outermost {...} object.
    if not text.startswith("{"):
        i = text.find("{")
        if i != -1:
            text = text[i:]
    if not text.endswith("}"):
        j = text.rfind("}")
        if j != -1:
            text = text[:j + 1]
    return text.strip()


def _fallback_stock_response(ticker: str, raw: str) -> dict:
    """Build a best-effort response when JSON parsing fails."""
    return {
        "company_name": ticker,
        "valuation": {
            "bear": 0,
            "base": 0,
            "bull": 0,
            "methodology": "Parse error — see raw_analysis",
        },
        "investment_thesis": raw[:500],
        "bull_case": "",
        "bear_case": "",
        "key_risks": [],
        "quality_score": {"moat": 0, "management": 0, "financial_health": 0, "growth_runway": 0, "overall": 0},
        "sector_outlook": "",
        "sentiment_summary": "",
    }
