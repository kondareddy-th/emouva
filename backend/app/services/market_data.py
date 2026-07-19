"""
Market data enrichment service using yfinance.
Used for earnings, company info, raw news, and batch price quotes.
"""

import hashlib
import logging
import time
from typing import Any

import yfinance as yf

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[float, Any]] = {}

CACHE_60S = 60
CACHE_1H = 3600
CACHE_24H = 86400


def _get_cached(key: str, ttl: float) -> Any | None:
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < ttl:
            return data
        del _cache[key]
    return None


def _set_cached(key: str, data: Any) -> None:
    _cache[key] = (time.time(), data)


def invalidate_cache(symbol: str | None = None) -> None:
    """Clear cached data. If symbol given, clear only that symbol's entries."""
    if symbol is None:
        _cache.clear()
        return
    keys_to_remove = [k for k in _cache if symbol in k]
    for k in keys_to_remove:
        del _cache[k]


def get_earnings(symbol: str, years: int = 3) -> dict:
    """Get quarterly earnings from income statement (last N years)."""
    cache_key = f"earnings_{symbol}_{years}"
    cached = _get_cached(cache_key, CACHE_24H)
    if cached is not None:
        return cached

    try:
        ticker = yf.Ticker(symbol)
        stmt = ticker.quarterly_income_stmt

        if stmt is None or stmt.empty:
            return {"symbol": symbol, "quarters": []}

        quarters = []
        cutoff_cols = min(len(stmt.columns), years * 4)
        for col in stmt.columns[:cutoff_cols]:
            date_str = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)

            revenue = _safe_float(stmt, "Total Revenue", col)
            net_income = _safe_float(stmt, "Net Income", col)
            # EPS: try diluted first, then basic
            eps = _safe_float(stmt, "Diluted EPS", col)
            if eps is None:
                eps = _safe_float(stmt, "Basic EPS", col)

            quarters.append({
                "date": date_str,
                "revenue": revenue,
                "net_income": net_income,
                "eps": eps,
            })

        result = {"symbol": symbol, "quarters": quarters}
        _set_cached(cache_key, result)
        return result

    except Exception:
        logger.exception("Failed to fetch earnings for %s", symbol)
        return {"symbol": symbol, "quarters": []}


def _fund_to_info(f: dict) -> dict:
    """Map the provider-normalized fundamentals (market_providers.get_fundamentals) back
    onto the yfinance `.info` key names, so get_company_info's mapping below is unchanged
    regardless of which vendor actually answered."""
    return {
        "longName": f.get("name"), "sector": f.get("sector"), "industry": f.get("industry"),
        "country": f.get("country"), "marketCap": f.get("market_cap"), "currentPrice": f.get("price"),
        "trailingPE": f.get("pe_ratio"), "forwardPE": f.get("forward_pe"), "trailingPegRatio": f.get("peg_ratio"),
        "priceToBook": f.get("price_to_book"), "priceToSalesTrailing12Months": f.get("price_to_sales"),
        "beta": f.get("beta"), "fiftyTwoWeekHigh": f.get("year_high"), "fiftyTwoWeekLow": f.get("year_low"),
        "fiftyDayAverage": f.get("sma50"), "twoHundredDayAverage": f.get("sma200"),
        "profitMargins": f.get("profit_margins"), "operatingMargins": f.get("operating_margins"),
        "grossMargins": f.get("gross_margins"), "returnOnEquity": f.get("return_on_equity"),
        "returnOnAssets": f.get("return_on_assets"), "revenueGrowth": f.get("revenue_growth"),
        "earningsGrowth": f.get("earnings_growth"), "freeCashflow": f.get("free_cash_flow"),
        "operatingCashflow": f.get("operating_cash_flow"), "debtToEquity": f.get("debt_to_equity"),
        "currentRatio": f.get("current_ratio"), "dividendYield": f.get("dividend_yield"),
        "targetMeanPrice": f.get("target_mean_price"), "targetHighPrice": f.get("target_high_price"),
        "targetLowPrice": f.get("target_low_price"), "numberOfAnalystOpinions": f.get("number_of_analysts"),
        "trailingEps": f.get("eps_trailing"), "epsForward": f.get("eps_forward"),
    }


def get_company_info(symbol: str) -> dict:
    """Company fundamentals + quality metrics + ratios, via the resilient provider chain
    (FMP → finnhub → yfinance). Same key shape as before — nothing downstream changes."""
    cache_key = f"info_{symbol}"
    cached = _get_cached(cache_key, CACHE_24H)
    if cached is not None:
        return cached

    try:
        from app.services import market_providers as mp
        f = mp.get_fundamentals(symbol)
        if not f:
            return {"symbol": symbol}
        info = _fund_to_info(f)

        result = {
            "symbol": symbol,
            "name": info.get("longName") or info.get("shortName") or symbol,
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "country": info.get("country", "Unknown"),
            "description": info.get("longBusinessSummary", ""),
            # Valuation
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("trailingPegRatio"),
            "price_to_book": info.get("priceToBook"),
            "price_to_sales": info.get("priceToSalesTrailing12Months"),
            "enterprise_to_ebitda": info.get("enterpriseToEbitda"),
            "enterprise_to_revenue": info.get("enterpriseToRevenue"),
            # Price & Momentum
            "beta": info.get("beta"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "fifty_day_average": info.get("fiftyDayAverage"),
            "two_hundred_day_average": info.get("twoHundredDayAverage"),
            "avg_volume": info.get("averageVolume"),
            # Profitability & Quality
            "profit_margins": info.get("profitMargins"),
            "operating_margins": info.get("operatingMargins"),
            "gross_margins": info.get("grossMargins"),
            "return_on_equity": info.get("returnOnEquity"),
            "return_on_assets": info.get("returnOnAssets"),
            # Growth
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "earnings_quarterly_growth": info.get("earningsQuarterlyGrowth"),
            # Cash Flow & Balance Sheet
            "free_cash_flow": info.get("freeCashflow"),
            "operating_cash_flow": info.get("operatingCashflow"),
            "total_cash": info.get("totalCash"),
            "total_debt": info.get("totalDebt"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            # Dividends & Shareholder Returns
            "dividend_yield": info.get("dividendYield"),
            "dividend_rate": info.get("dividendRate"),
            "payout_ratio": info.get("payoutRatio"),
            "five_year_avg_dividend_yield": info.get("fiveYearAvgDividendYield"),
            # Ownership & Analyst
            "held_percent_insiders": info.get("heldPercentInsiders"),
            "held_percent_institutions": info.get("heldPercentInstitutions"),
            "analyst_recommendation": info.get("averageAnalystRating"),
            "recommendation_key": info.get("recommendationKey"),
            "target_mean_price": info.get("targetMeanPrice"),
            "target_high_price": info.get("targetHighPrice"),
            "target_low_price": info.get("targetLowPrice"),
            "number_of_analysts": info.get("numberOfAnalystOpinions"),
            # Short Interest
            "short_ratio": info.get("shortRatio"),
            "short_percent_of_float": info.get("shortPercentOfFloat"),
            # Per-Share
            "eps_trailing": info.get("trailingEps"),
            "eps_forward": info.get("epsForward"),
            "revenue_per_share": info.get("revenuePerShare"),
            "book_value": info.get("bookValue"),
            # Size
            "full_time_employees": info.get("fullTimeEmployees"),
            # forward-looking enrichment (from the provider fundamentals, not yfinance .info)
            "forward_eps_est": f.get("forward_eps_est"), "forward_revenue_est": f.get("forward_revenue_est"),
            "grade_trend": f.get("grade_trend"),
        }

        _set_cached(cache_key, result)
        return result

    except Exception:
        logger.exception("Failed to fetch company info for %s", symbol)
        return {"symbol": symbol}


def get_news(symbol: str) -> list[dict]:
    """Get recent news headlines for a symbol."""
    cache_key = f"news_{symbol}"
    cached = _get_cached(cache_key, CACHE_1H)
    if cached is not None:
        return cached

    try:
        ticker = yf.Ticker(symbol)
        raw_news = ticker.news or []

        articles = []
        for item in raw_news[:10]:
            content = item.get("content", {}) if isinstance(item, dict) else {}
            articles.append({
                "title": content.get("title") or item.get("title", ""),
                "publisher": content.get("provider", {}).get("displayName", "")
                    if isinstance(content.get("provider"), dict)
                    else item.get("publisher", ""),
                "link": content.get("canonicalUrl", {}).get("url", "")
                    if isinstance(content.get("canonicalUrl"), dict)
                    else item.get("link", ""),
                "published": content.get("pubDate", "") or item.get("providerPublishTime", ""),
                "symbol": symbol,
            })

        _set_cached(cache_key, articles)
        return articles

    except Exception:
        logger.exception("Failed to fetch news for %s", symbol)
        return []


def get_batch_quotes(symbols: list[str]) -> list[dict]:
    """Latest prices via the RESILIENT provider chain (FMP → finnhub → yfinance; see
    market_providers.py). Returns [{symbol, price, previous_close, change_pct}, ...].
    60s server-side cache. FMP has no bulk endpoint on our plan, so this is one call per
    symbol (paced under the vendor's rate cap) — the reliability is worth the extra calls."""
    if not symbols:
        return []
    unique = sorted(set(s.upper() for s in symbols))
    cache_key = "batch_quotes_" + hashlib.md5(",".join(unique).encode()).hexdigest()
    cached = _get_cached(cache_key, CACHE_60S)
    if cached is not None:
        return cached
    from app.services import market_providers as mp
    quotes: list[dict] = []
    for sym in unique:
        q = mp.get_quote(sym)
        if not q or not q.get("price"):
            continue
        price, prev = q["price"], q.get("prev_close")
        chg = ((price - prev) / prev * 100) if prev else 0.0
        quotes.append({"symbol": sym, "price": round(price, 2),
                       "previous_close": round(prev, 2) if prev else None, "change_pct": round(chg, 2)})
    _set_cached(cache_key, quotes)
    return quotes


def _yf_batch_quotes(symbols: list[str]) -> list[dict]:
    """The original yfinance batch path (yf.download) — kept as the yfinance provider's
    quote source and the last-resort fallback. Same shape as get_batch_quotes."""
    unique = sorted(set(s.upper() for s in symbols))
    try:
        # Batch download: 5 days of daily data gives us today + previous close
        df = yf.download(unique, period="5d", interval="1d", progress=False, threads=True)

        quotes: list[dict] = []

        if df is None or df.empty:
            return []

        close_all = df["Close"]
        is_frame = hasattr(close_all, "columns")     # DataFrame (multi-symbol, or single as a 1-col MultiIndex)
        for symbol in unique:
            try:
                # Robust to every yfinance shape: multi-symbol frame, single-symbol
                # 1-col frame, or a flat Series.
                if is_frame:
                    if symbol in close_all.columns:
                        close_series = close_all[symbol]
                    elif len(unique) == 1:
                        close_series = close_all.iloc[:, 0]
                    else:
                        continue
                else:
                    close_series = close_all

                if close_series is None or close_series.dropna().empty:
                    continue

                clean = close_series.dropna()
                if len(clean) < 2:
                    continue

                price = float(clean.iloc[-1])
                prev_close = float(clean.iloc[-2])
                change_pct = ((price - prev_close) / prev_close * 100) if prev_close > 0 else 0.0

                quotes.append({
                    "symbol": symbol,
                    "price": round(price, 2),
                    "previous_close": round(prev_close, 2),
                    "change_pct": round(change_pct, 2),
                })
            except Exception:
                logger.debug("Failed to extract quote for %s", symbol)
                continue

        return quotes

    except Exception:
        logger.debug("yfinance batch quotes failed for %d symbols", len(unique))
        return []


def get_annual_financials(symbol: str, years: int = 5) -> dict:
    """Get annual income statement + balance sheet + cash flow for trend analysis.
    Returns revenue, net income, FCF, margins, ROIC for each year.
    """
    cache_key = f"annual_financials_{symbol}_{years}"
    cached = _get_cached(cache_key, CACHE_24H)
    if cached is not None:
        return cached

    try:
        ticker = yf.Ticker(symbol)
        inc = ticker.income_stmt
        bs = ticker.balance_sheet
        cf = ticker.cashflow

        annual = []
        if inc is not None and not inc.empty:
            for col in inc.columns[:years]:
                date_str = col.strftime("%Y") if hasattr(col, "strftime") else str(col)[:4]

                revenue = _safe_float(inc, "Total Revenue", col)
                net_income = _safe_float(inc, "Net Income", col)
                operating_income = _safe_float(inc, "Operating Income", col)
                gross_profit = _safe_float(inc, "Gross Profit", col)
                ebitda = _safe_float(inc, "EBITDA", col)

                # Cash flow
                fcf = None
                op_cf = None
                capex = None
                if cf is not None and not cf.empty and col in cf.columns:
                    op_cf = _safe_float(cf, "Operating Cash Flow", col)
                    capex = _safe_float(cf, "Capital Expenditure", col)
                    if op_cf is not None and capex is not None:
                        fcf = op_cf + capex  # capex is negative

                # Balance sheet for ROIC
                total_equity = None
                total_debt_val = None
                total_cash_val = None
                if bs is not None and not bs.empty and col in bs.columns:
                    total_equity = _safe_float(bs, "Stockholders Equity", col) or _safe_float(bs, "Total Equity Gross Minority Interest", col)
                    total_debt_val = _safe_float(bs, "Total Debt", col)
                    total_cash_val = _safe_float(bs, "Cash And Cash Equivalents", col)

                # Computed metrics
                gross_margin = (gross_profit / revenue) if revenue and gross_profit else None
                operating_margin = (operating_income / revenue) if revenue and operating_income else None
                net_margin = (net_income / revenue) if revenue and net_income else None

                # ROIC = NOPAT / Invested Capital
                # NOPAT ≈ Operating Income × (1 - tax rate), approximate tax rate as 21%
                roic = None
                if operating_income and total_equity is not None and total_debt_val is not None:
                    nopat = operating_income * 0.79  # after 21% tax
                    invested_capital = total_equity + total_debt_val - (total_cash_val or 0)
                    if invested_capital > 0:
                        roic = nopat / invested_capital

                # FCF Yield (annualized)
                fcf_yield = None
                info = _get_cached(f"info_{symbol}", CACHE_24H)
                if fcf and info and info.get("market_cap"):
                    fcf_yield = fcf / info["market_cap"]

                annual.append({
                    "year": date_str,
                    "revenue": revenue,
                    "net_income": net_income,
                    "operating_income": operating_income,
                    "gross_profit": gross_profit,
                    "ebitda": ebitda,
                    "fcf": fcf,
                    "operating_cash_flow": op_cf,
                    "capex": capex,
                    "gross_margin": round(gross_margin, 4) if gross_margin else None,
                    "operating_margin": round(operating_margin, 4) if operating_margin else None,
                    "net_margin": round(net_margin, 4) if net_margin else None,
                    "roic": round(roic, 4) if roic else None,
                    "fcf_yield": round(fcf_yield, 4) if fcf_yield else None,
                    "total_equity": total_equity,
                    "total_debt": total_debt_val,
                })

        result = {"symbol": symbol, "annual": annual}
        _set_cached(cache_key, result)
        return result

    except Exception:
        logger.exception("Failed to fetch annual financials for %s", symbol)
        return {"symbol": symbol, "annual": []}


def compute_piotroski_score(symbol: str) -> dict:
    """Compute Piotroski F-Score (0-9) from financial statements.
    Higher = stronger financial health. ≥7 = strong, ≤3 = weak.
    """
    cache_key = f"piotroski_{symbol}"
    cached = _get_cached(cache_key, CACHE_24H)
    if cached is not None:
        return cached

    try:
        ticker = yf.Ticker(symbol)
        inc = ticker.income_stmt
        bs = ticker.balance_sheet
        cf = ticker.cashflow

        if inc is None or inc.empty or len(inc.columns) < 2:
            return {"symbol": symbol, "score": None, "details": {}}

        curr, prev = inc.columns[0], inc.columns[1]
        score = 0
        details = {}

        # --- Profitability (4 points) ---
        # 1. Positive net income
        ni = _safe_float(inc, "Net Income", curr)
        if ni and ni > 0:
            score += 1
            details["net_income_positive"] = True
        else:
            details["net_income_positive"] = False

        # 2. Positive operating cash flow
        ocf = _safe_float(cf, "Operating Cash Flow", curr) if cf is not None and not cf.empty and curr in cf.columns else None
        if ocf and ocf > 0:
            score += 1
            details["ocf_positive"] = True
        else:
            details["ocf_positive"] = False

        # 3. ROA improving (net income / total assets)
        ta_curr = _safe_float(bs, "Total Assets", curr) if bs is not None and not bs.empty and curr in bs.columns else None
        ta_prev = _safe_float(bs, "Total Assets", prev) if bs is not None and not bs.empty and prev in bs.columns else None
        ni_prev = _safe_float(inc, "Net Income", prev)
        if ni and ta_curr and ni_prev and ta_prev and ta_curr > 0 and ta_prev > 0:
            roa_curr = ni / ta_curr
            roa_prev = ni_prev / ta_prev
            if roa_curr > roa_prev:
                score += 1
                details["roa_improving"] = True
            else:
                details["roa_improving"] = False
        else:
            details["roa_improving"] = None

        # 4. Cash flow > net income (earnings quality)
        if ocf and ni and ocf > ni:
            score += 1
            details["earnings_quality"] = True
        else:
            details["earnings_quality"] = False

        # --- Leverage & Liquidity (3 points) ---
        # 5. Decreasing long-term debt ratio
        ltd_curr = _safe_float(bs, "Long Term Debt", curr) if bs is not None and not bs.empty and curr in bs.columns else None
        ltd_prev = _safe_float(bs, "Long Term Debt", prev) if bs is not None and not bs.empty and prev in bs.columns else None
        if ltd_curr is not None and ltd_prev is not None and ta_curr and ta_prev:
            ratio_curr = ltd_curr / ta_curr if ta_curr > 0 else 0
            ratio_prev = ltd_prev / ta_prev if ta_prev > 0 else 0
            if ratio_curr <= ratio_prev:
                score += 1
                details["leverage_decreasing"] = True
            else:
                details["leverage_decreasing"] = False
        else:
            details["leverage_decreasing"] = None

        # 6. Improving current ratio
        ca_curr = _safe_float(bs, "Current Assets", curr) if bs is not None and not bs.empty and curr in bs.columns else None
        cl_curr = _safe_float(bs, "Current Liabilities", curr) if bs is not None and not bs.empty and curr in bs.columns else None
        ca_prev = _safe_float(bs, "Current Assets", prev) if bs is not None and not bs.empty and prev in bs.columns else None
        cl_prev = _safe_float(bs, "Current Liabilities", prev) if bs is not None and not bs.empty and prev in bs.columns else None
        if ca_curr and cl_curr and ca_prev and cl_prev and cl_curr > 0 and cl_prev > 0:
            cr_curr = ca_curr / cl_curr
            cr_prev = ca_prev / cl_prev
            if cr_curr > cr_prev:
                score += 1
                details["current_ratio_improving"] = True
            else:
                details["current_ratio_improving"] = False
        else:
            details["current_ratio_improving"] = None

        # 7. No new share issuance (dilution)
        shares_curr = _safe_float(inc, "Diluted Average Shares", curr) or _safe_float(inc, "Basic Average Shares", curr)
        shares_prev = _safe_float(inc, "Diluted Average Shares", prev) or _safe_float(inc, "Basic Average Shares", prev)
        if shares_curr and shares_prev:
            if shares_curr <= shares_prev:
                score += 1
                details["no_dilution"] = True
            else:
                details["no_dilution"] = False
        else:
            details["no_dilution"] = None

        # --- Operating Efficiency (2 points) ---
        # 8. Improving gross margin
        gp_curr = _safe_float(inc, "Gross Profit", curr)
        gp_prev = _safe_float(inc, "Gross Profit", prev)
        rev_curr = _safe_float(inc, "Total Revenue", curr)
        rev_prev = _safe_float(inc, "Total Revenue", prev)
        if gp_curr and rev_curr and gp_prev and rev_prev and rev_curr > 0 and rev_prev > 0:
            gm_curr = gp_curr / rev_curr
            gm_prev = gp_prev / rev_prev
            if gm_curr > gm_prev:
                score += 1
                details["gross_margin_improving"] = True
            else:
                details["gross_margin_improving"] = False
        else:
            details["gross_margin_improving"] = None

        # 9. Improving asset turnover
        if rev_curr and ta_curr and rev_prev and ta_prev and ta_curr > 0 and ta_prev > 0:
            at_curr = rev_curr / ta_curr
            at_prev = rev_prev / ta_prev
            if at_curr > at_prev:
                score += 1
                details["asset_turnover_improving"] = True
            else:
                details["asset_turnover_improving"] = False
        else:
            details["asset_turnover_improving"] = None

        result = {"symbol": symbol, "score": score, "details": details}
        _set_cached(cache_key, result)
        return result

    except Exception:
        logger.exception("Failed to compute Piotroski for %s", symbol)
        return {"symbol": symbol, "score": None, "details": {}}


def get_peer_comparison(symbol: str) -> dict:
    """Get valuation medians for the stock's sector/industry peers."""
    cache_key = f"peers_{symbol}"
    cached = _get_cached(cache_key, CACHE_24H)
    if cached is not None:
        return cached

    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        industry = info.get("industry", "")
        sector = info.get("sector", "")

        # Sector ETF medians as proxy (faster than scraping individual peers)
        sector_etfs = {
            "Technology": "XLK", "Financial Services": "XLF", "Healthcare": "XLV",
            "Consumer Cyclical": "XLY", "Communication Services": "XLC",
            "Industrials": "XLI", "Consumer Defensive": "XLP", "Energy": "XLE",
            "Utilities": "XLU", "Real Estate": "XLRE", "Basic Materials": "XLB",
        }
        etf_symbol = sector_etfs.get(sector)

        sector_pe = None
        if etf_symbol:
            try:
                etf = yf.Ticker(etf_symbol)
                etf_info = etf.info or {}
                sector_pe = etf_info.get("trailingPE")
            except Exception:
                pass

        # Stock's own 5Y P/E range from historical data (use current info for now)
        pe = info.get("trailingPE")
        fwd_pe = info.get("forwardPE")

        result = {
            "symbol": symbol,
            "sector": sector,
            "industry": industry,
            "stock_pe": pe,
            "stock_fwd_pe": fwd_pe,
            "sector_pe": sector_pe,
            "sector_etf": etf_symbol,
            "pe_vs_sector": round(((pe / sector_pe) - 1) * 100, 1) if pe and sector_pe and sector_pe > 0 else None,
        }

        _set_cached(cache_key, result)
        return result

    except Exception:
        logger.exception("Failed to get peer comparison for %s", symbol)
        return {"symbol": symbol, "sector": "", "industry": ""}


def _fx_rate(from_ccy: str, to_ccy: str) -> float | None:
    """Units of `to_ccy` per 1 `from_ccy` (e.g. _fx_rate('TWD','USD') ≈ 0.031). 1.0 when
    the currencies match; None if the rate can't be fetched. Cached 24h."""
    if not from_ccy or not to_ccy or from_ccy == to_ccy:
        return 1.0
    key = f"fx_{from_ccy}_{to_ccy}"
    cached = _get_cached(key, CACHE_24H)
    if cached is not None:
        return cached
    try:
        r = yf.Ticker(f"{from_ccy}{to_ccy}=X").info.get("regularMarketPrice")
        r = float(r) if r else None
    except Exception:
        r = None
    if r:
        _set_cached(key, r)
    return r


def compute_dcf(symbol: str) -> dict:
    """Compute a simple DCF (Discounted Cash Flow) fair value per share.

    Methodology:
    - Uses trailing FCF as the starting point
    - Projects 5 years of FCF growth (capped at reasonable rates)
    - Discounts at WACC estimated from CAPM (risk-free + beta × equity premium)
    - Terminal value via perpetuity growth model (2.5% long-term growth)
    - Fair value = (PV of projected FCFs + PV of terminal value) / shares outstanding
    - Entry price = fair value × 0.80 (20% margin of safety)

    Returns dict with: fair_value, entry_price, assumptions, and per-year projections.
    """
    cache_key = f"dcf_{symbol}"
    cached = _get_cached(cache_key, CACHE_24H)
    if cached is not None:
        return cached

    try:
        from app.services import market_providers as mp
        info = mp.get_fundamentals(symbol) or {}   # provider-normalized (FMP FCF is far more reliable than yfinance's)

        fcf = info.get("free_cash_flow")
        shares = info.get("shares_outstanding")
        beta = info.get("beta")
        market_cap = info.get("market_cap")
        rev_growth = info.get("revenue_growth")  # YoY as decimal (0.24 = 24%)
        current_price = info.get("price")

        if not fcf or not shares or shares <= 0 or fcf <= 0:
            return {"symbol": symbol, "fair_value": None, "entry_price": None,
                    "reason": "Insufficient data (negative or missing FCF)"}

        # --- Currency alignment (foreign ADRs) ---
        # yfinance reports financials in `financialCurrency` but the ADR price/shares in
        # `currency` (USD). For e.g. TSMC, freeCashflow is in TWD — dividing TWD cash flows
        # by USD-scaled shares inflated fair value ~32×. Convert FCF to the price currency.
        fin_ccy, price_ccy = info.get("financial_currency"), info.get("currency")
        if fin_ccy and price_ccy and fin_ccy != price_ccy:
            fx = _fx_rate(fin_ccy, price_ccy)
            if not fx:   # can't align currencies → don't emit a wrong number
                return {"symbol": symbol, "fair_value": None, "entry_price": None,
                        "reason": f"FX {fin_ccy}->{price_ccy} unavailable — can't value in price currency"}
            fcf = float(fcf) * fx

        # --- WACC estimation via CAPM ---
        risk_free = 0.043  # ~4.3% (10Y Treasury yield as of 2026)
        equity_premium = 0.055  # ~5.5% long-term equity risk premium
        beta_val = max(0.5, min(beta or 1.0, 2.5))  # Clamp beta 0.5-2.5
        wacc = risk_free + beta_val * equity_premium
        wacc = max(0.08, min(wacc, 0.15))  # Clamp WACC 8%-15%

        # --- Growth rate estimation ---
        # Use revenue growth but cap it for realism
        if rev_growth and rev_growth > 0:
            # Phase 1 (Years 1-3): actual growth rate, capped at 30%
            phase1_growth = min(rev_growth, 0.30)
            # Phase 2 (Years 4-5): decay toward long-term
            phase2_growth = min(phase1_growth * 0.6, 0.15)
        else:
            phase1_growth = 0.05  # Conservative 5% for low/negative growth
            phase2_growth = 0.03

        terminal_growth = 0.025  # 2.5% perpetuity growth

        # --- Project FCFs ---
        projections = []
        current_fcf = float(fcf)
        total_pv = 0.0

        for year in range(1, 6):
            growth = phase1_growth if year <= 3 else phase2_growth
            projected_fcf = current_fcf * (1 + growth)
            discount_factor = 1 / ((1 + wacc) ** year)
            pv = projected_fcf * discount_factor
            total_pv += pv

            projections.append({
                "year": year,
                "fcf": round(projected_fcf),
                "growth": round(growth * 100, 1),
                "pv": round(pv),
            })
            current_fcf = projected_fcf

        # --- Terminal value ---
        terminal_fcf = current_fcf * (1 + terminal_growth)
        terminal_value = terminal_fcf / (wacc - terminal_growth)
        terminal_pv = terminal_value / ((1 + wacc) ** 5)
        total_pv += terminal_pv

        # --- Per-share values ---
        fair_value_per_share = total_pv / shares
        entry_price = fair_value_per_share * 0.80  # 20% margin of safety

        # Sanity check: if fair value is wildly different from current price, note it
        upside = ((fair_value_per_share - current_price) / current_price * 100) if current_price else None

        result = {
            "symbol": symbol,
            "fair_value": round(fair_value_per_share, 2),
            "entry_price": round(entry_price, 2),
            "current_price": round(current_price, 2) if current_price else None,
            "upside_pct": round(upside, 1) if upside else None,
            "margin_of_safety_pct": 20,
            "assumptions": {
                "starting_fcf": round(fcf),
                "wacc": round(wacc * 100, 1),
                "beta": round(beta_val, 2),
                "phase1_growth": round(phase1_growth * 100, 1),
                "phase2_growth": round(phase2_growth * 100, 1),
                "terminal_growth": round(terminal_growth * 100, 1),
                "shares_outstanding": shares,
            },
            "projections": projections,
            "terminal_value": round(terminal_pv),
        }

        _set_cached(cache_key, result)
        return result

    except Exception:
        logger.exception("Failed to compute DCF for %s", symbol)
        return {"symbol": symbol, "fair_value": None, "entry_price": None}


def _safe_float(df, row_label: str, col) -> float | None:
    """Safely extract a float from a DataFrame cell."""
    try:
        if row_label in df.index:
            val = df.loc[row_label, col]
            if val is not None and str(val) != "nan":
                return float(val)
    except Exception:
        pass
    return None
