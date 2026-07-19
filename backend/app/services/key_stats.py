"""Key statistics + INSIGHTS engine — built to beat Yahoo's key-statistics page.

Yahoo dumps numbers; we compute context and signal:
  * composite scores: quality, financial health, growth, valuation
  * derived metrics Yahoo omits: ROIC, FCF margin/yield, Rule-of-40,
    Piotroski F-score, Altman Z, net cash, buyback-vs-dilution
  * multi-year trends (margins, revenue, FCF, share count) for sparklines
  * plain-language insights (rule-based — no LLM, so it's fast & free)

Heavy yfinance pulls are cached in-memory (fundamentals are quarterly); the
live price is overlaid per request so price-dependent metrics stay current.
"""
from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

_RAW_CACHE: dict[str, tuple[float, dict]] = {}
_RAW_TTL = 12 * 3600  # fundamentals change quarterly; 12h is plenty


# ── helpers ───────────────────────────────────────────────────────────────────
def _num(x) -> float | None:
    try:
        import math
        v = float(x)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None


def _series(df, *names) -> list[float | None]:
    """Most-recent-first list of a statement row, matching the first name present."""
    if df is None:
        return []
    try:
        idx = list(df.index)
    except Exception:
        return []
    for name in names:
        if name in idx:
            return [_num(v) for v in df.loc[name].tolist()]
    return []


def _cagr(latest: float | None, oldest: float | None, years: int) -> float | None:
    if not latest or not oldest or oldest <= 0 or latest <= 0 or years <= 0:
        return None
    return (latest / oldest) ** (1 / years) - 1


def _money(v: float | None) -> str:
    if v is None:
        return "—"
    a = abs(v)
    for div, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= div:
            return f"${v / div:.2f}{suf}"
    return f"${v:,.0f}"


def _pct(v: float | None, mult: bool = True) -> str:
    if v is None:
        return "—"
    return f"{v * 100:.1f}%" if mult else f"{v:.1f}%"


def _x(v: float | None) -> str:
    return "—" if v is None else f"{v:.1f}x"


def _item(label, value, context="", tone="neutral") -> dict:
    return {"label": label, "value": value, "context": context, "tone": tone}


# ── raw fetch (cached) ─────────────────────────────────────────────────────────
def _fetch_raw(ticker: str) -> dict:
    hit = _RAW_CACHE.get(ticker)
    if hit and time.time() - hit[0] < _RAW_TTL:
        return hit[1]

    import yfinance as yf
    t = yf.Ticker(ticker)
    raw: dict[str, Any] = {"info": {}, "inc": None, "bal": None, "cf": None, "qinc": None}
    try:
        raw["info"] = t.info or {}
    except Exception:
        raw["info"] = {}
    for key, attr in (("inc", "income_stmt"), ("bal", "balance_sheet"),
                      ("cf", "cashflow"), ("qinc", "quarterly_income_stmt")):
        try:
            raw[key] = getattr(t, attr)
        except Exception:
            raw[key] = None
    _RAW_CACHE[ticker] = (time.time(), raw)
    return raw


def _live_price(ticker: str) -> float | None:
    """Freshest yfinance price (fast_info) — used when the caller passes no price."""
    try:
        import yfinance as yf
        fi = yf.Ticker(ticker).fast_info
        return _num(fi.get("lastPrice") or fi.get("last_price"))
    except Exception:
        return None


# ── main ───────────────────────────────────────────────────────────────────────
def build_key_stats(ticker: str, price: float | None = None) -> dict:
    ticker = ticker.upper()
    raw = _fetch_raw(ticker)
    info = raw["info"]
    g = info.get

    if price is None:
        price = _live_price(ticker)  # freshest yfinance quote when caller didn't pass one
    px = price or _num(g("currentPrice")) or _num(g("regularMarketPrice"))
    shares = _num(g("sharesOutstanding"))
    mktcap = (px * shares) if (px and shares) else _num(g("marketCap"))

    # --- statement series (most-recent-first) ---
    rev = _series(raw["inc"], "Total Revenue", "Operating Revenue")
    gp = _series(raw["inc"], "Gross Profit")
    op_inc = _series(raw["inc"], "Operating Income", "Total Operating Income As Reported")
    net = _series(raw["inc"], "Net Income", "Net Income Common Stockholders",
                  "Net Income From Continuing Operation Net Minority Interest")
    ebit = _series(raw["inc"], "EBIT", "Operating Income")
    ebitda = _series(raw["inc"], "EBITDA", "Normalized EBITDA")
    int_exp = _series(raw["inc"], "Interest Expense")
    dil_sh = _series(raw["inc"], "Diluted Average Shares")
    equity = _series(raw["bal"], "Stockholders Equity", "Common Stock Equity")
    tot_debt = _series(raw["bal"], "Total Debt")
    inv_cap = _series(raw["bal"], "Invested Capital")
    work_cap = _series(raw["bal"], "Working Capital")
    ret_earn = _series(raw["bal"], "Retained Earnings")
    tot_liab = _series(raw["bal"], "Total Liabilities Net Minority Interest", "Total Liabilities")
    tot_assets = _series(raw["bal"], "Total Assets")
    fcf = _series(raw["cf"], "Free Cash Flow")
    capex = _series(raw["cf"], "Capital Expenditure")
    buyback = _series(raw["cf"], "Repurchase Of Capital Stock")
    ocf_s = _series(raw["cf"], "Operating Cash Flow", "Cash Flow From Continuing Operating Activities")

    def latest(s):
        return s[0] if s else None

    # --- valuation (live-price aware) ---
    eps_t = _num(g("trailingEps"))
    pe = (px / eps_t) if (px and eps_t and eps_t > 0) else _num(g("trailingPE"))
    fpe = _num(g("forwardPE"))
    ps = (mktcap / latest(rev)) if (mktcap and latest(rev)) else _num(g("priceToSalesTrailing12Months"))
    pb = _num(g("priceToBook"))
    ev = _num(g("enterpriseValue"))
    fcf_ttm = _num(g("freeCashflow")) or latest(fcf)
    fcf_yield = (fcf_ttm / mktcap) if (fcf_ttm and mktcap) else None
    peg = _num(g("pegRatio"))

    # --- profitability ---
    gm = _num(g("grossMargins"))
    om = _num(g("operatingMargins"))
    nm = _num(g("profitMargins"))
    roe = _num(g("returnOnEquity"))
    roa = _num(g("returnOnAssets"))
    # ROIC = NOPAT / Invested Capital  (NOPAT ≈ EBIT * (1 - 21%))
    roic = None
    if latest(ebit) and latest(inv_cap) and latest(inv_cap) > 0:
        roic = (latest(ebit) * 0.79) / latest(inv_cap)
    gm_series = [(_g / _r) if (_g and _r) else None for _g, _r in zip(gp, rev)]

    # --- growth ---
    rev_g = _num(g("revenueGrowth"))
    earn_g = _num(g("earningsGrowth")) or _num(g("earningsQuarterlyGrowth"))
    rev_cagr3 = _cagr(rev[0], rev[3], 3) if len(rev) >= 4 else None
    fcf_margin = (fcf_ttm / latest(rev)) if (fcf_ttm and latest(rev)) else None
    rule40 = ((rev_g or 0) + (fcf_margin if fcf_margin is not None else (om or 0))) if rev_g is not None else None

    # --- health ---
    cash = _num(g("totalCash"))
    debt = _num(g("totalDebt")) or latest(tot_debt)
    net_cash = (cash - debt) if (cash is not None and debt is not None) else None
    cur_ratio = _num(g("currentRatio"))
    quick = _num(g("quickRatio"))
    int_cov = (latest(ebit) / abs(latest(int_exp))) if (latest(ebit) and latest(int_exp)) else None
    piotroski = _piotroski(rev, gp, net, equity, tot_debt, ocf_s, dil_sh)
    altman = _altman(latest(rev), latest(ebit), latest(work_cap), latest(ret_earn),
                     mktcap, latest(tot_liab) or debt,
                     latest(tot_assets) or ((latest(equity) or 0) + (latest(tot_liab) or debt or 0)))

    # --- share count trend (buyback vs dilution) ---
    sh_chg = None
    if len(dil_sh) >= 4 and dil_sh[0] and dil_sh[3]:
        sh_chg = (dil_sh[0] / dil_sh[3]) ** (1 / 3) - 1  # annualized

    # --- technicals ---
    hi = _num(g("fiftyTwoWeekHigh")); lo = _num(g("fiftyTwoWeekLow"))
    pos52 = ((px - lo) / (hi - lo)) if (px and hi and lo and hi > lo) else None
    dma50 = _num(g("fiftyDayAverage")); dma200 = _num(g("twoHundredDayAverage"))
    beta = _num(g("beta"))

    # === scores ===
    scores = _scores(roic, gm, om, fcf_margin, rev_g, rev_cagr3, earn_g, rule40,
                     piotroski, altman, net_cash, int_cov, cur_ratio,
                     fcf_yield, fpe, pe, peg)

    # === insights (rule-based) ===
    insights = _insights(ticker, rev_cagr3, rev_g, gm, gm_series, om, roic, roe,
                         net_cash, cash, debt, int_cov, rule40, piotroski, altman,
                         fcf_margin, sh_chg, pe, fpe, fcf_yield, pos52, dma200, px,
                         _num(g("shortPercentOfFloat")))

    return {
        "symbol": ticker,
        "name": g("longName") or g("shortName") or ticker,
        "sector": g("sector"), "industry": g("industry"),
        "price": px,
        "scores": scores,
        "insights": insights,
        "sections": {
            "valuation": [
                _item("Market Cap", _money(mktcap)),
                _item("Enterprise Value", _money(ev)),
                _item("Trailing P/E", _x(pe), _pe_ctx(pe, fpe)),
                _item("Forward P/E", _x(fpe), "earnings expected to grow" if (pe and fpe and fpe < pe) else ""),
                _item("PEG", _x(peg), "≤1 = growth cheap vs P/E" if peg else "", _tone(peg, 1.0, 2.0, invert=True)),
                _item("Price / Sales", _x(ps)),
                _item("Price / Book", _x(pb)),
                _item("EV / EBITDA", _x((ev / latest(ebitda)) if (ev and latest(ebitda)) else None)),
                _item("FCF Yield", _pct(fcf_yield), "owner earnings vs price", _tone(fcf_yield, 0.04, 0.02)),
            ],
            "profitability": [
                _item("Gross Margin", _pct(gm), _trend_ctx(gm_series), _tone(gm, 0.4, 0.2)),
                _item("Operating Margin", _pct(om), "", _tone(om, 0.2, 0.05)),
                _item("Net Margin", _pct(nm), "", _tone(nm, 0.15, 0.0)),
                _item("ROIC", _pct(roic), "return on invested capital", _tone(roic, 0.15, 0.07)),
                _item("ROE", _pct(roe), "", _tone(roe, 0.15, 0.05)),
                _item("ROA", _pct(roa), "", _tone(roa, 0.08, 0.02)),
            ],
            "growth": [
                _item("Revenue Growth (YoY)", _pct(rev_g), "", _tone(rev_g, 0.15, 0.0)),
                _item("Revenue CAGR (3y)", _pct(rev_cagr3), "", _tone(rev_cagr3, 0.15, 0.0)),
                _item("Earnings Growth", _pct(earn_g), "", _tone(earn_g, 0.15, 0.0)),
                _item("FCF Margin", _pct(fcf_margin), "", _tone(fcf_margin, 0.15, 0.0)),
                _item("Rule of 40", f"{rule40 * 100:.0f}" if rule40 is not None else "—",
                      "growth% + FCF margin%; >40 is elite", _tone(rule40, 0.40, 0.20)),
            ],
            "health": [
                _item("Total Cash", _money(cash)),
                _item("Total Debt", _money(debt)),
                _item("Net Cash / (Debt)", _money(net_cash),
                      "net cash = no leverage risk" if (net_cash and net_cash > 0) else "carries net debt",
                      _tone(net_cash, 0, -1e12)),
                _item("Current Ratio", _x(cur_ratio), "", _tone(cur_ratio, 1.5, 1.0)),
                _item("Quick Ratio", _x(quick), "", _tone(quick, 1.0, 0.7)),
                _item("Interest Coverage", _x(int_cov), "EBIT / interest", _tone(int_cov, 6, 2)),
                _item("Piotroski F-score", f"{piotroski}/9" if piotroski is not None else "—",
                      "fundamental quality (9 = best)", _tone(piotroski, 7, 4)),
                _item("Altman Z-score", f"{altman:.1f}" if altman is not None else "—",
                      _altman_ctx(altman), _tone(altman, 3.0, 1.8)),
            ],
            "cashflow": [
                _item("Operating Cash Flow", _money(_num(g("operatingCashflow")) or latest(ocf_s))),
                _item("Free Cash Flow", _money(fcf_ttm)),
                _item("CapEx", _money(latest(capex))),
                _item("Buybacks (last yr)", _money(latest(buyback))),
                _item("Share Count Trend (3y)", _pct(sh_chg) if sh_chg is not None else "—",
                      "buying back shares" if (sh_chg and sh_chg < 0) else ("diluting" if sh_chg else ""),
                      _tone(-sh_chg if sh_chg is not None else None, 0.0, -0.03)),
            ],
            "per_share": [
                _item("Trailing EPS", _x(eps_t).replace("x", "") if eps_t else "—"),
                _item("Forward EPS", f"{_num(g('forwardEps')):.2f}" if _num(g("forwardEps")) else "—"),
                _item("Book Value / Share", f"{_num(g('bookValue')):.2f}" if _num(g("bookValue")) else "—"),
                _item("Revenue / Share", f"{(latest(rev)/shares):.2f}" if (latest(rev) and shares) else "—"),
                _item("FCF / Share", f"{(fcf_ttm/shares):.2f}" if (fcf_ttm and shares) else "—"),
            ],
            "technicals": [
                _item("52-Week Range", f"{_money(lo)} – {_money(hi)}".replace("$", "")
                      if (hi and lo) else "—",
                      f"{pos52 * 100:.0f}% of range" if pos52 is not None else "",
                      _tone(pos52, 0.5, 0.2) if pos52 is not None else "neutral"),
                _item("vs 50-day MA", _pct((px / dma50 - 1)) if (px and dma50) else "—",
                      "above" if (px and dma50 and px > dma50) else "below",
                      _tone((px / dma50 - 1) if (px and dma50) else None, 0, -0.05)),
                _item("vs 200-day MA", _pct((px / dma200 - 1)) if (px and dma200) else "—",
                      "long-term uptrend" if (px and dma200 and px > dma200) else "below 200-DMA",
                      _tone((px / dma200 - 1) if (px and dma200) else None, 0, -0.05)),
                _item("Beta", f"{beta:.2f}" if beta else "—", "vol vs market"),
                _item("Avg Volume", _money(_num(g("averageVolume"))).replace("$", "")
                      if _num(g("averageVolume")) else "—"),
            ],
            "ownership": [
                _item("Insiders", _pct(_num(g("heldPercentInsiders")))),
                _item("Institutions", _pct(_num(g("heldPercentInstitutions")))),
                _item("Short % of Float", _pct(_num(g("shortPercentOfFloat"))),
                      "elevated short interest" if (_num(g("shortPercentOfFloat")) or 0) > 0.1 else "",
                      _tone(-(_num(g("shortPercentOfFloat")) or 0), -0.05, -0.10)),
                _item("Short Ratio (days)", _x(_num(g("shortRatio"))).replace("x", "")
                      if _num(g("shortRatio")) else "—"),
                _item("Float", _money(_num(g("floatShares"))).replace("$", "")
                      if _num(g("floatShares")) else "—"),
            ],
        },
        "trends": {
            "revenue": list(reversed([v for v in rev[:4] if v is not None])),
            "gross_margin": list(reversed([v for v in gm_series[:4] if v is not None])),
            "fcf": list(reversed([v for v in fcf[:4] if v is not None])),
            "shares": list(reversed([v for v in dil_sh[:4] if v is not None])),
        },
        "dividend": _dividend(info, px),
        "source": "yfinance",
    }


# ── composite signals ──────────────────────────────────────────────────────────
def _piotroski(rev, gp, net, equity, debt, ocf, shares) -> int | None:
    """Piotroski F-score (0-9): profitability, leverage/liquidity, efficiency."""
    try:
        if len(net) < 2 or len(ocf) < 2:
            return None
        s = 0
        ni0, ni1 = net[0], net[1]
        cfo0 = ocf[0]
        ta0 = equity[0] if equity else None  # proxy; full assets not always present
        # profitability
        if ni0 and ni0 > 0: s += 1
        if cfo0 and cfo0 > 0: s += 1
        if ni0 is not None and ni1 is not None and ni0 > ni1: s += 1   # ROA improving (NI proxy)
        if cfo0 is not None and ni0 is not None and cfo0 > ni0: s += 1  # accruals quality
        # leverage / liquidity
        if len(debt) >= 2 and debt[0] is not None and debt[1] is not None and debt[0] <= debt[1]: s += 1
        # share issuance (no dilution)
        if len(shares) >= 2 and shares[0] is not None and shares[1] is not None and shares[0] <= shares[1] * 1.01: s += 1
        # efficiency: gross margin up + revenue up
        if len(gp) >= 2 and len(rev) >= 2 and gp[0] and gp[1] and rev[0] and rev[1]:
            if (gp[0] / rev[0]) > (gp[1] / rev[1]): s += 1
            if rev[0] > rev[1]: s += 1
        # earnings quality bonus
        if ni0 and ni1 and ni1 != 0 and ni0 / ni1 > 1.1: s += 1
        return min(s, 9)
    except Exception:
        return None


def _altman(rev, ebit, wc, re, mktcap, tot_liab, total_assets) -> float | None:
    """Altman Z (non-financial). Capped: anything >3 is 'safe', so we don't show
    the absurd values low-liability mega-caps produce in the market-leverage term."""
    try:
        ta = total_assets
        if not ta or ta <= 0:
            return None
        tl = tot_liab or 0
        z = (1.2 * ((wc or 0) / ta) + 1.4 * ((re or 0) / ta) + 3.3 * ((ebit or 0) / ta)
             + 0.6 * ((mktcap or 0) / (tl or 1)) + 1.0 * ((rev or 0) / ta))
        return round(min(z, 15.0), 2)
    except Exception:
        return None


def _scores(roic, gm, om, fcf_m, rev_g, cagr, earn_g, rule40, piotroski, altman,
            net_cash, int_cov, cur_ratio, fcf_yield, fpe, pe, peg) -> dict:
    def band(v, good, ok):
        if v is None:
            return None
        return 100 if v >= good else (65 if v >= ok else 30)

    def avg(vals):
        vs = [v for v in vals if v is not None]
        return round(sum(vs) / len(vs)) if vs else 0

    quality = avg([band(roic, 0.15, 0.07), band(gm, 0.4, 0.2), band(om, 0.2, 0.07),
                   band(fcf_m, 0.15, 0.05)])
    health = avg([band(piotroski, 7, 4) if piotroski is not None else None,
                  band(altman, 3.0, 1.8), 100 if (net_cash and net_cash > 0) else 40,
                  band(int_cov, 6, 2), band(cur_ratio, 1.5, 1.0)])
    growth = avg([band(rev_g, 0.20, 0.07), band(cagr, 0.15, 0.05), band(earn_g, 0.15, 0.0),
                  band(rule40, 0.40, 0.20)])
    # valuation: cheaper = higher score
    val_bits = []
    if fcf_yield is not None:
        val_bits.append(100 if fcf_yield >= 0.05 else (65 if fcf_yield >= 0.03 else 30))
    if peg is not None:
        val_bits.append(100 if peg <= 1 else (60 if peg <= 2 else 25))
    if fpe is not None:
        val_bits.append(100 if fpe <= 15 else (60 if fpe <= 30 else 25))
    value = round(sum(val_bits) / len(val_bits)) if val_bits else 0

    overall = round((quality * 0.3 + health * 0.25 + growth * 0.25 + value * 0.2))
    return {"quality": quality, "health": health, "growth": growth,
            "value": value, "overall": overall}


# ── insights (plain language, rule-based) ──────────────────────────────────────
def _insights(sym, cagr, rev_g, gm, gm_series, om, roic, roe, net_cash, cash, debt,
              int_cov, rule40, piotroski, altman, fcf_m, sh_chg, pe, fpe, fcf_yield,
              pos52, dma200, px, short_pct) -> list[str]:
    out = []
    if cagr is not None:
        q = "exceptional" if cagr > 0.3 else "strong" if cagr > 0.15 else "modest" if cagr > 0.05 else "sluggish"
        out.append(f"Revenue compounded {cagr*100:.0f}%/yr over 3 years — {q}.")
    elif rev_g is not None:
        out.append(f"Revenue grew {rev_g*100:.0f}% year-over-year.")
    if len(gm_series) >= 4 and gm_series[0] and gm_series[3]:
        d = (gm_series[0] - gm_series[3]) * 10000
        if abs(d) > 150:
            out.append(f"Gross margin {'expanded' if d>0 else 'compressed'} {abs(d):.0f} bps over 3 years to {gm*100:.0f}%.")
    if roic is not None:
        q = "elite" if roic > 0.25 else "strong" if roic > 0.15 else "adequate" if roic > 0.07 else "weak"
        out.append(f"ROIC of {roic*100:.0f}% — {q} capital efficiency.")
    if net_cash is not None:
        if net_cash > 0:
            out.append(f"Net cash position of {_money(net_cash)} — no balance-sheet leverage risk.")
        elif int_cov is not None:
            out.append(f"Carries {_money(-net_cash)} net debt; interest covered {int_cov:.0f}x by EBIT.")
    if rule40 is not None and fcf_m is not None and rev_g is not None:
        out.append(f"Rule of 40 = {rule40*100:.0f} ({rev_g*100:.0f}% growth + {fcf_m*100:.0f}% FCF margin)"
                   + (" — elite." if rule40 > 0.4 else "."))
    if piotroski is not None and piotroski >= 7:
        out.append(f"Piotroski F-score {piotroski}/9 — very strong fundamental quality.")
    elif piotroski is not None and piotroski <= 3:
        out.append(f"Piotroski F-score {piotroski}/9 — weak fundamentals, watch closely.")
    if pe and fpe and fpe < pe * 0.8:
        out.append(f"Trades at {fpe:.0f}x forward vs {pe:.0f}x trailing — the market expects earnings to grow ~{(pe/fpe-1)*100:.0f}%.")
    if fcf_yield is not None and fcf_yield > 0.05:
        out.append(f"FCF yield of {fcf_yield*100:.1f}% — generates real owner earnings relative to price.")
    if sh_chg is not None:
        if sh_chg < -0.01:
            out.append(f"Buying back stock — share count down ~{abs(sh_chg)*100:.0f}%/yr.")
        elif sh_chg > 0.03:
            out.append(f"Diluting shareholders ~{sh_chg*100:.0f}%/yr — a drag on per-share value.")
    if short_pct and short_pct > 0.1:
        out.append(f"Short interest is {short_pct*100:.0f}% of float — elevated bearish positioning.")
    if pos52 is not None and pos52 > 0.95:
        out.append("Trading near its 52-week high.")
    elif pos52 is not None and pos52 < 0.1:
        out.append("Trading near its 52-week low.")
    return out[:9]


def _dividend(info, px) -> dict | None:
    dy = _num(info.get("dividendYield"))
    rate = _num(info.get("dividendRate"))
    if not dy and not rate:
        return None
    return {
        "yield": _pct(dy / 100 if (dy and dy > 1) else dy),
        "rate": f"${rate:.2f}" if rate else "—",
        "payout_ratio": _pct(_num(info.get("payoutRatio"))),
        "ex_date": info.get("exDividendDate"),
    }


# ── small context strings ──────────────────────────────────────────────────────
def _pe_ctx(pe, fpe):
    if pe and fpe and fpe < pe:
        return "earnings growing into the multiple"
    if pe and pe > 40:
        return "rich multiple — priced for growth"
    return ""


def _trend_ctx(series):
    s = [v for v in series if v is not None]
    if len(s) >= 2:
        return "expanding" if s[0] > s[-1] else "contracting"
    return ""


def _altman_ctx(z):
    if z is None:
        return ""
    return "safe zone" if z > 3 else "grey zone" if z > 1.8 else "distress zone"


def _tone(v, good, bad, invert=False):
    """good/bad thresholds -> 'good'|'warn'|'bad'. invert: lower is better."""
    if v is None:
        return "neutral"
    if invert:
        return "good" if v <= good else "warn" if v <= bad else "bad"
    return "good" if v >= good else "warn" if v >= bad else "bad"
