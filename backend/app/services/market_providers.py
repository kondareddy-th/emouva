"""Market-data providers with automatic fallback — so one vendor going down never
takes the platform down.

WHY THIS EXISTS
    We were 100% on yfinance (Yahoo), which rate-limits bursts (HTTP 401 "Invalid
    Crumb"), hangs on stalled sockets (it once deadlocked the pre-market refresh), and
    ships unreliable free-cash-flow (badly understated — and our DCF runs on FCF).
    This layer puts a reliable paid API (FMP) first, finnhub second (it covers the
    international ADRs FMP gates on our plan), and yfinance last — and NORMALIZES all
    three to ONE shape so the rest of the app (fair_value, trend, central stats, DCF)
    neither knows nor cares which vendor answered.

HOW TO SWITCH / DROP A PROVIDER  (this is the resilience knob)
    The order lives in settings.market_provider_order (env MARKET_PROVIDER_ORDER, CSV),
    e.g. "fmp,finnhub,yfinance". To make a vendor primary, put it first. To retire a
    vendor that's gone down permanently, delete it from the list — nothing else changes,
    because every caller goes through get_quote()/get_fundamentals()/get_history() which
    just walk the order until one returns usable data. Adding a NEW vendor = write a
    provider class with quote()/fundamentals()/history() and register it in _PROVIDERS.

RATE LIMITS  (respected via a thread-safe per-provider min-interval limiter)
    FMP:      ~300 req/min per plan  +  a HARD 30 req/sec cap  → HTTP 429 on exceed.
              We pace to ~285/min (≈0.21s between calls), which also stays under 30/sec.
    finnhub:  60 req/min (free)      → ≈1.05s between calls.
    yfinance: unofficial; paced gently and treated as last resort only.

NORMALIZED SHAPES  (every provider returns these keys, or None for what it can't supply)
    quote:        {price, market_cap, prev_close, year_high, year_low, sma50, sma200, currency}
    fundamentals: a superset dict (see _EMPTY_FUND) covering everything get_company_info,
                  compute_dcf, fair_value and the central stats gate need. `financial_currency`
                  is the statements' currency; when it differs from `currency` (a foreign ADR),
                  compute_dcf converts FCF. FMP's FCF is derived from FCF-yield × USD market cap,
                  so for FMP it's already in USD (financial_currency == currency) — no conversion.
    history:      [close, close, ...] daily closes, oldest→newest (for the trend read).
"""
from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request

from app.config import settings

logger = logging.getLogger(__name__)

_UA = {"User-Agent": "emouva/1.0"}


# ── shared HTTP + rate limiting ─────────────────────────────────────────────
class _RateLimiter:
    """Serialize a provider's calls to a minimum interval (thread-safe). Bounds the
    global request rate regardless of how many worker threads call concurrently, so we
    never trip a vendor's per-second / per-minute cap."""

    def __init__(self, min_interval: float):
        self._min = min_interval
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self):
        with self._lock:
            gap = time.time() - self._last
            if gap < self._min:
                time.sleep(self._min - gap)
            self._last = time.time()


def _http_json(url: str, limiter: _RateLimiter, timeout: float = 12.0):
    """GET → parsed JSON, or None on any failure (never raises, never hangs past
    `timeout`). 429 is logged distinctly so we can see if we're pushing a vendor's cap."""
    limiter.wait()
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=timeout)
        return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            logger.warning("provider 429 (rate limited): %s", url.split("?")[0])
        elif e.code not in (402, 403, 404):   # 402/403 = plan-gated symbol (expected for some ADRs)
            logger.debug("provider HTTP %s: %s", e.code, url.split("?")[0])
        return None
    except Exception as e:  # noqa: BLE001 — timeout / network / parse → fail-open to the next provider
        logger.debug("provider error %s: %s", type(e).__name__, url.split("?")[0])
        return None


def _num(x):
    try:
        return float(x) if x is not None and x != "" else None
    except (TypeError, ValueError):
        return None


# the full normalized fundamentals shape (keys every consumer may read; None = unknown)
_EMPTY_FUND = {
    "provider": None, "name": None, "sector": None, "industry": None, "country": None,
    "currency": None, "financial_currency": None,
    "price": None, "market_cap": None, "shares_outstanding": None, "beta": None,
    "sma50": None, "sma200": None, "year_high": None, "year_low": None, "prev_close": None,
    "gross_margins": None, "operating_margins": None, "profit_margins": None,
    "return_on_equity": None, "return_on_assets": None, "debt_to_equity": None, "current_ratio": None,
    "pe_ratio": None, "forward_pe": None, "peg_ratio": None, "price_to_book": None, "price_to_sales": None,
    "revenue_growth": None, "earnings_growth": None,
    "free_cash_flow": None, "operating_cash_flow": None,
    "eps_trailing": None, "eps_forward": None,
    "target_mean_price": None, "target_low_price": None, "target_high_price": None, "number_of_analysts": None,
    "dividend_yield": None,
    # forward-looking enrichment (FMP-only; None from other providers)
    "forward_eps_est": None, "forward_revenue_est": None, "grade_trend": None,
}


# grade ranking for turning analyst up/down-grades into a net signal
_GRADE_RANK = {"strong sell": 0, "sell": 1, "underperform": 2, "underweight": 2, "reduce": 2,
               "hold": 3, "neutral": 3, "market perform": 3, "sector perform": 3, "equal-weight": 3, "in-line": 3,
               "accumulate": 4, "outperform": 4, "overweight": 4, "buy": 4, "add": 4, "sector outperform": 4,
               "strong buy": 5, "conviction buy": 5}


def _grade_summary(grades: list) -> str | None:
    """Compact 90-day analyst-action signal from FMP /grades, e.g. '90d: 3↑ 1↓ 4='."""
    if not grades:
        return None
    up = down = same = 0
    for g in grades[:25]:
        n = _GRADE_RANK.get(str(g.get("newGrade", "")).lower())
        p = _GRADE_RANK.get(str(g.get("previousGrade", "")).lower())
        if n is None:
            continue
        if p is None or n == p:
            same += 1
        elif n > p:
            up += 1
        else:
            down += 1
    if up == down == same == 0:
        return None
    return f"90d analyst actions: {up}↑ {down}↓ {same}="


# ── FMP (primary) ───────────────────────────────────────────────────────────
class _FMP:
    name = "fmp"
    base = "https://financialmodelingprep.com/stable"
    _rl = _RateLimiter(0.21)   # ≈285/min, under the 300/min + 30/sec caps

    def _ok(self):
        return bool(settings.fmp_api_key)

    def _get(self, path: str):
        d = _http_json(f"{self.base}/{path}&apikey={settings.fmp_api_key}", self._rl)
        if isinstance(d, list):
            return d[0] if d else None
        if isinstance(d, dict) and "Error Message" not in d and "Special Endpoint" not in str(d):
            return d
        return None   # plan-gated symbol / error → let the caller fall through to finnhub

    def _get_list(self, path: str):
        d = _http_json(f"{self.base}/{path}&apikey={settings.fmp_api_key}", self._rl)
        return d if isinstance(d, list) else []

    def quote(self, sym: str):
        q = self._get(f"quote?symbol={sym}")
        if not q or _num(q.get("price")) is None:
            return None
        return {"price": _num(q.get("price")), "market_cap": _num(q.get("marketCap")),
                "prev_close": _num(q.get("previousClose")), "year_high": _num(q.get("yearHigh")),
                "year_low": _num(q.get("yearLow")), "sma50": _num(q.get("priceAvg50")),
                "sma200": _num(q.get("priceAvg200")), "currency": "USD"}

    def fundamentals(self, sym: str):
        q = self._get(f"quote?symbol={sym}")
        if not q or _num(q.get("price")) is None:
            return None   # not covered by FMP (e.g. a gated ADR) → fall through
        prof = self._get(f"profile?symbol={sym}") or {}
        km = self._get(f"key-metrics-ttm?symbol={sym}") or {}
        ra = self._get(f"ratios-ttm?symbol={sym}") or {}
        pt = self._get(f"price-target-consensus?symbol={sym}") or {}
        gr = self._get(f"financial-growth?symbol={sym}&limit=1") or {}

        price, mcap = _num(q.get("price")), _num(q.get("marketCap"))
        pe = _num(ra.get("priceToEarningsRatioTTM"))
        # FCF from yield × USD market cap → already in USD, so no currency conversion needed.
        fcf_yield = _num(km.get("freeCashFlowYieldTTM"))
        fcf = fcf_yield * mcap if (fcf_yield is not None and mcap) else None
        f = dict(_EMPTY_FUND)
        f.update({
            "provider": self.name,
            "name": prof.get("companyName") or sym, "sector": prof.get("sector"),
            "industry": prof.get("industry"), "country": prof.get("country"),
            "currency": prof.get("currency") or "USD", "financial_currency": prof.get("currency") or "USD",
            "price": price, "market_cap": mcap,
            "shares_outstanding": (mcap / price) if (mcap and price) else None,
            "beta": _num(prof.get("beta")),
            "sma50": _num(q.get("priceAvg50")), "sma200": _num(q.get("priceAvg200")),
            "year_high": _num(q.get("yearHigh")), "year_low": _num(q.get("yearLow")),
            "prev_close": _num(q.get("previousClose")),
            "gross_margins": _num(ra.get("grossProfitMarginTTM")),
            "operating_margins": _num(ra.get("operatingProfitMarginTTM")),
            "profit_margins": _num(ra.get("netProfitMarginTTM")),
            "return_on_equity": _num(km.get("returnOnEquityTTM")),
            "return_on_assets": _num(km.get("returnOnAssetsTTM")),
            "debt_to_equity": _num(ra.get("debtToEquityRatioTTM")),
            "current_ratio": _num(ra.get("currentRatioTTM")) or _num(km.get("currentRatioTTM")),
            "pe_ratio": pe, "peg_ratio": _num(ra.get("priceToEarningsGrowthRatioTTM")),
            "price_to_book": _num(ra.get("priceToBookRatioTTM")),
            "price_to_sales": _num(ra.get("priceToSalesRatioTTM")),
            "revenue_growth": _num(gr.get("revenueGrowth")),
            "earnings_growth": _num(gr.get("netIncomeGrowth")),
            "free_cash_flow": fcf,
            "eps_trailing": (price / pe) if (pe and price) else None,
            "target_mean_price": _num(pt.get("targetConsensus")),
            "target_low_price": _num(pt.get("targetLow")), "target_high_price": _num(pt.get("targetHigh")),
            "dividend_yield": _num(prof.get("lastDividend")),
        })
        # forward-looking enrichment (upgraded plan): next-FY consensus + analyst-grade trend
        fwd = _nearest_future(self._get_list(f"analyst-estimates?symbol={sym}&period=annual&limit=8"))
        if fwd:
            f["forward_eps_est"] = _num(fwd.get("epsAvg"))
            f["forward_revenue_est"] = _num(fwd.get("revenueAvg"))
        f["grade_trend"] = _grade_summary(self._get_list(f"grades?symbol={sym}&limit=20"))
        return f

    def history(self, sym: str):
        d = _http_json(f"{self.base}/historical-price-eod/light?symbol={sym}&apikey={settings.fmp_api_key}", self._rl)
        if not isinstance(d, list) or not d:
            return None
        # FMP returns newest→oldest; trend wants oldest→newest closes.
        closes = [_num(row.get("price") or row.get("close")) for row in reversed(d)]
        closes = [c for c in closes if c is not None]
        return closes or None


# ── finnhub (fallback — covers the ADRs FMP gates) ──────────────────────────
class _Finnhub:
    name = "finnhub"
    base = "https://finnhub.io/api/v1"
    _rl = _RateLimiter(1.05)   # 60/min free tier

    def _ok(self):
        return bool(settings.finnhub_api_key)

    def _get(self, path: str):
        return _http_json(f"{self.base}/{path}&token={settings.finnhub_api_key}", self._rl)

    def quote(self, sym: str):
        q = self._get(f"quote?symbol={sym}") or {}
        price = _num(q.get("c"))
        if not price:
            return None
        return {"price": price, "market_cap": None, "prev_close": _num(q.get("pc")),
                "year_high": None, "year_low": None, "sma50": None, "sma200": None, "currency": "USD"}

    def fundamentals(self, sym: str):
        # quote gives the USD ADR price; `metric` gives currency-INDEPENDENT ratios
        # (margins, ROE, PE, 52wk) — usable even when the underlying reports in EUR/JPY.
        # No analyst targets (premium) and FCF is skipped for ADRs (currency-messy) — this
        # is a degraded-but-useful fallback for names FMP won't serve.
        q = self._get(f"quote?symbol={sym}") or {}
        price = _num(q.get("c"))
        if not price:
            return None
        m = (self._get(f"stock/metric?symbol={sym}&metric=all") or {}).get("metric") or {}
        prof = self._get(f"stock/profile2?symbol={sym}") or {}
        f = dict(_EMPTY_FUND)
        f.update({
            "provider": self.name, "name": prof.get("name") or sym,
            "sector": prof.get("finnhubIndustry"), "country": prof.get("country"),
            "currency": "USD", "financial_currency": prof.get("currency") or "USD",
            "price": price, "prev_close": _num(q.get("pc")),
            "beta": _num(m.get("beta")),
            "year_high": _num(m.get("52WeekHigh")), "year_low": _num(m.get("52WeekLow")),
            "gross_margins": _pct(m.get("grossMarginTTM")), "operating_margins": _pct(m.get("operatingMarginTTM")),
            "profit_margins": _pct(m.get("netProfitMarginTTM")),
            "return_on_equity": _pct(m.get("roeTTM")), "return_on_assets": _pct(m.get("roaTTM")),
            "current_ratio": _num(m.get("currentRatioQuarterly")),
            "pe_ratio": _num(m.get("peTTM")), "price_to_book": _num(m.get("pbQuarterly")),
            "price_to_sales": _num(m.get("psTTM")),
            "revenue_growth": _pct(m.get("revenueGrowthTTMYoy")),
            "earnings_growth": _pct(m.get("epsGrowthTTMYoy")),
            "eps_trailing": _num(m.get("epsTTM")),
        })
        return f

    def history(self, sym: str):
        return None   # finnhub candles are premium on the free tier → let yfinance serve history


# finnhub reports margins/returns as PERCENT (e.g. 47.8), the rest of the app expects a
# fraction (0.478) like yfinance/FMP — normalize.
def _pct(x):
    v = _num(x)
    return v / 100.0 if v is not None else None


# ── yfinance (last resort) ──────────────────────────────────────────────────
class _YFinance:
    name = "yfinance"
    _rl = _RateLimiter(0.3)

    def _ok(self):
        return True

    def _info(self, sym: str):
        self._rl.wait()
        try:
            import yfinance as yf
            return yf.Ticker(sym).info or {}
        except Exception:  # noqa: BLE001
            return {}

    def quote(self, sym: str):
        from app.services.market_data import _yf_batch_quotes   # the original yfinance batch path
        rows = _yf_batch_quotes([sym])
        if rows and _num(rows[0].get("price")):
            r = rows[0]
            return {"price": _num(r.get("price")), "market_cap": None, "prev_close": _num(r.get("previous_close")),
                    "year_high": None, "year_low": None, "sma50": None, "sma200": None, "currency": "USD"}
        return None

    def fundamentals(self, sym: str):
        i = self._info(sym)
        if not i:
            return None
        f = dict(_EMPTY_FUND)
        f.update({
            "provider": self.name,
            "name": i.get("longName") or i.get("shortName") or sym, "sector": i.get("sector"),
            "industry": i.get("industry"), "country": i.get("country"),
            "currency": i.get("currency") or "USD", "financial_currency": i.get("financialCurrency") or "USD",
            "price": _num(i.get("currentPrice")) or _num(i.get("regularMarketPrice")),
            "market_cap": _num(i.get("marketCap")), "shares_outstanding": _num(i.get("sharesOutstanding")),
            "beta": _num(i.get("beta")),
            "sma50": _num(i.get("fiftyDayAverage")), "sma200": _num(i.get("twoHundredDayAverage")),
            "year_high": _num(i.get("fiftyTwoWeekHigh")), "year_low": _num(i.get("fiftyTwoWeekLow")),
            "gross_margins": _num(i.get("grossMargins")), "operating_margins": _num(i.get("operatingMargins")),
            "profit_margins": _num(i.get("profitMargins")),
            "return_on_equity": _num(i.get("returnOnEquity")), "return_on_assets": _num(i.get("returnOnAssets")),
            "debt_to_equity": _num(i.get("debtToEquity")), "current_ratio": _num(i.get("currentRatio")),
            "pe_ratio": _num(i.get("trailingPE")), "forward_pe": _num(i.get("forwardPE")),
            "peg_ratio": _num(i.get("trailingPegRatio")), "price_to_book": _num(i.get("priceToBook")),
            "price_to_sales": _num(i.get("priceToSalesTrailing12Months")),
            "revenue_growth": _num(i.get("revenueGrowth")), "earnings_growth": _num(i.get("earningsGrowth")),
            "free_cash_flow": _num(i.get("freeCashflow")), "operating_cash_flow": _num(i.get("operatingCashflow")),
            "eps_trailing": _num(i.get("trailingEps")), "eps_forward": _num(i.get("epsForward")),
            "target_mean_price": _num(i.get("targetMeanPrice")), "target_low_price": _num(i.get("targetLowPrice")),
            "target_high_price": _num(i.get("targetHighPrice")),
            "number_of_analysts": _num(i.get("numberOfAnalystOpinions")),
            "dividend_yield": _num(i.get("dividendYield")),
        })
        return f

    def history(self, sym: str):
        self._rl.wait()
        try:
            import yfinance as yf
            h = yf.Ticker(sym).history(period="8mo", interval="1d", auto_adjust=True)
            closes = [float(x) for x in h["Close"].dropna().tolist()]
            return closes or None
        except Exception:  # noqa: BLE001
            return None


_PROVIDERS = {"fmp": _FMP(), "finnhub": _Finnhub(), "yfinance": _YFinance()}


def _order() -> list:
    names = [p.strip() for p in (settings.market_provider_order or "").split(",") if p.strip()]
    return [_PROVIDERS[n] for n in names if n in _PROVIDERS and _PROVIDERS[n]._ok()] or [_PROVIDERS["yfinance"]]


# ── in-process cache — one fetch per symbol/day; also keeps us under vendor caps.
# (fundamentals is read by BOTH compute_dcf and get_company_info, so caching here avoids
# fetching the same name twice.) Simple {sym: (ts, value)} with a TTL per capability.
_CACHE: dict[str, tuple[float, object]] = {}
_TTL = {"q": 60, "f": 86400, "h": 86400}


def _cached(kind: str, symbol: str, producer):
    key = f"{kind}:{symbol.upper()}"
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < _TTL[kind]:
        return hit[1]
    val = producer()
    if val is not None:
        _CACHE[key] = (time.time(), val)
    return val


# ── public facade — walk the fallback chain until one vendor answers ─────────
def get_quote(symbol: str) -> dict | None:
    def _run():
        for p in _order():
            try:
                q = p.quote(symbol)
            except Exception:  # noqa: BLE001
                q = None
            if q and q.get("price"):
                q["provider"] = p.name
                return q
        return None
    return _cached("q", symbol, _run)


def get_fundamentals(symbol: str) -> dict | None:
    def _run():
        for p in _order():
            try:
                f = p.fundamentals(symbol)
            except Exception:  # noqa: BLE001
                f = None
            if f and f.get("price"):
                return f
        return None
    return _cached("f", symbol, _run)


def get_history(symbol: str) -> list | None:
    def _run():
        for p in _order():
            try:
                h = p.history(symbol)
            except Exception:  # noqa: BLE001
                h = None
            if h and len(h) >= 30:
                return h
        return None
    return _cached("h", symbol, _run)


def _nearest_future(rows: list) -> dict | None:
    """The analyst-estimate row for the NEXT fiscal year (earliest date ≥ today)."""
    import datetime
    today = datetime.date.today().isoformat()
    fut = sorted([r for r in rows if isinstance(r, dict) and str(r.get("date", "")) >= today],
                 key=lambda r: r["date"])
    return fut[0] if fut else (rows[0] if rows else None)


# ── FMP-only rich-data accessors (not part of the normalized abstraction) — used by the
# earnings-triggered foundational thesis. Return [] when FMP isn't configured/available. ──
def _fmp():
    return _PROVIDERS["fmp"]


def fmp_earnings_calendar(from_date: str, to_date: str) -> list:
    p = _fmp()
    if not p._ok():
        return []
    d = _http_json(f"{p.base}/earnings-calendar?from={from_date}&to={to_date}&apikey={settings.fmp_api_key}", p._rl, timeout=25)
    return d if isinstance(d, list) else []


def fmp_income_quarter(symbol: str, limit: int = 2) -> list:
    p = _fmp()
    return p._get_list(f"income-statement?symbol={symbol}&period=quarter&limit={limit}") if p._ok() else []


def fmp_grades(symbol: str, limit: int = 12) -> list:
    p = _fmp()
    return p._get_list(f"grades?symbol={symbol}&limit={limit}") if p._ok() else []


def fmp_news(symbol: str, limit: int = 6) -> list:
    p = _fmp()
    return p._get_list(f"news/stock?symbols={symbol}&limit={limit}") if p._ok() else []


def search_symbols(query: str, limit: int = 10) -> list:
    """Public search facade: FMP when configured (best quality), else a free
    yfinance fallback — so ticker search works on a keyless self-hosted install."""
    out = fmp_search(query, limit)
    return out if out else _yf_search(query, limit)


def _yf_search(query: str, limit: int = 10) -> list:
    """Free-tier search via yfinance (no key). Same shape as fmp_search; filtered
    to US exchanges. Defensive: yf.Search is newer API — any failure → []."""
    q = query.strip()
    if not q:
        return []
    us = {"NMS", "NGM", "NCM", "NYQ", "ASE", "NASDAQ", "NYSE", "AMEX"}
    try:
        import yfinance as yf
        quotes = yf.Search(q, max_results=25).quotes or []
        out: dict[str, dict] = {}
        for r in quotes:
            sym = (r.get("symbol") or "").upper()
            ex = (r.get("exchange") or "").upper()
            if not sym or "." in sym or ex not in us:
                continue
            if (r.get("quoteType") or "").upper() not in ("EQUITY", "ETF"):
                continue
            out.setdefault(sym, {"symbol": sym, "name": r.get("shortname") or r.get("longname") or sym,
                                 "exchange": ex})
        return list(out.values())[:limit]
    except Exception:
        return []


def fmp_search(query: str, limit: int = 10) -> list:
    """Ticker/name search → [{symbol, name, exchange}], filtered to US-listed names (so
    everything returned is Robinhood-tradeable). Merges symbol-prefix + name matches."""
    p = _fmp()
    if not p._ok() or not query.strip():
        return []
    import urllib.parse
    q = urllib.parse.quote(query.strip())
    us = {"NASDAQ", "NYSE", "AMEX"}
    out: dict[str, dict] = {}
    for ep in (f"search-symbol?query={q}&limit=25", f"search-name?query={q}&limit=25"):
        for r in p._get_list(ep):
            sym = (r.get("symbol") or "").upper()
            ex = (r.get("exchange") or r.get("exchangeShortName") or "").upper()
            if not sym or "." in sym or ex not in us:   # skip foreign-suffixed / non-US listings
                continue
            out.setdefault(sym, {"symbol": sym, "name": r.get("name") or sym, "exchange": ex})
    return list(out.values())[:limit]
