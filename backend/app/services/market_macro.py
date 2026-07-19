"""
Market macro indicators service.

Computes three valuation signals:
1. Real Earnings Yield (REY) = Trailing E/P - CPI YoY%  [short-term signal]
2. Excess CAPE Yield (ECY) = 1/CAPE - Real 10Y Treasury  [Shiller's own best metric]
3. Equity Risk Premium (ERP) = E/P - Nominal 10Y Treasury  [Fed Model]

Data sources:
- Robert Shiller dataset (GitHub CSV): monthly SP500 price, reported earnings, CPI, CAPE, 10Y rate (1871-present)
- yfinance: real-time SPY P/E and ^TNX (10Y Treasury) for current month

Signal thresholds (based on Yardeni, Brightwood, and Shiller research):
  REY > 5%:   STRONG BUY  — every historical instance delivered strong forward returns
  REY 3-5%:   BUY         — near 60-year average (3.2%), stocks fairly to attractively valued
  REY 1.5-3%: HOLD        — positive but below average
  REY 0-1.5%: CAUTION     — historically poor forward returns
  REY < 0%:   DANGER      — preceded every major bear market (1987, 2000, 2008)

Refreshed every 1 hour via in-memory cache.
"""

import io
import logging
import time
from typing import Any

import numpy as np
import pandas as pd
import requests

logger = logging.getLogger(__name__)

# ── Cache ──

_cache: dict[str, tuple[float, Any]] = {}
CACHE_1H = 3600


def _get_cached(key: str) -> Any | None:
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < CACHE_1H:
            return data
        del _cache[key]
    return None


def _set_cached(key: str, data: Any) -> None:
    _cache[key] = (time.time(), data)


# ── Shiller Data ──

SHILLER_CSV_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"
SHILLER_WRAPPER_URL = "https://posix4e.github.io/shiller_wrapper_data/data/stock_market_data.csv"


def _fetch_shiller_data() -> pd.DataFrame | None:
    """Fetch Shiller's historical S&P 500 dataset with reported earnings, CPI, CAPE, 10Y rate."""
    cache_key = "shiller_raw"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    for url in [SHILLER_WRAPPER_URL, SHILLER_CSV_URL]:
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code != 200:
                continue

            df = pd.read_csv(io.StringIO(resp.text))

            # Normalize column names
            col_map = {}
            for c in df.columns:
                cl = c.strip().lower()
                if cl in ("date", "date_string"):
                    col_map[c] = "date"
                elif cl in ("sp500", "s&p comp.", "sp500_price"):
                    col_map[c] = "sp500"
                elif "earning" in cl and "real" not in cl and "pe" not in cl:
                    if "earnings" not in col_map.values():
                        col_map[c] = "earnings"
                elif cl in ("consumer price index", "cpi"):
                    col_map[c] = "cpi"
                elif cl in ("long interest rate", "long_interest_rate", "gs10"):
                    col_map[c] = "long_rate"
                elif cl in ("pe10", "cape"):
                    col_map[c] = "cape"

            df = df.rename(columns=col_map)

            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"], format="mixed", errors="coerce")
                df = df.dropna(subset=["date"])
                df = df.sort_values("date").reset_index(drop=True)

            for col in ["sp500", "earnings", "cpi", "long_rate", "cape"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            _set_cached(cache_key, df)
            logger.info("Loaded Shiller data: %d rows from %s", len(df), url.split("/")[-1])
            return df

        except Exception as e:
            logger.warning("Failed to fetch Shiller data from %s: %s", url, e)
            continue

    return None


def _get_live_data() -> dict:
    """Get current SPY P/E, 10Y Treasury, and S&P 500 price from yfinance."""
    cache_key = "live_macro"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    result: dict[str, Any] = {}
    try:
        import yfinance as yf

        spy = yf.Ticker("SPY")
        spy_info = spy.info or {}
        result["spy_pe"] = spy_info.get("trailingPE")
        result["spy_price"] = spy_info.get("regularMarketPrice") or spy_info.get("previousClose")
        result["spy_fwd_pe"] = spy_info.get("forwardPE")

        tnx = yf.Ticker("^TNX")
        tnx_info = tnx.info or {}
        result["treasury_10y"] = tnx_info.get("regularMarketPrice")

        gspc = yf.Ticker("^GSPC")
        gspc_info = gspc.info or {}
        result["sp500_price"] = gspc_info.get("regularMarketPrice") or gspc_info.get("previousClose")

        # QQQ for Nasdaq relative valuation
        qqq = yf.Ticker("QQQ")
        qqq_info = qqq.info or {}
        result["qqq_pe"] = qqq_info.get("trailingPE")

    except Exception as e:
        logger.warning("Failed to fetch live macro data: %s", e)

    _set_cached(cache_key, result)
    return result


# ── Computation ──

def compute_real_earnings_yield() -> dict:
    """Compute the full Real Earnings Yield + Excess CAPE Yield dataset from 1965 to today.

    Returns:
    {
        "historical": [{date, sp500, ey, cpi_yoy, real_ey, cape, cape_yield, ecy, long_rate, erp}, ...],
        "current": {ey, inflation, real_ey, ecy, erp, treasury_10y, sp500_price, cape, signal, ...},
        "forecast": [{date, real_ey}, ...],
        "stats": {avg, median, min, max, current_percentile, ...},
        "ecy_stats": {avg, median, current, ...},
        "nasdaq": {qqq_pe, relative_pe, ...},
    }
    """
    cache_key = "real_earnings_yield_v2"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    df = _fetch_shiller_data()
    if df is None or df.empty:
        return {"error": "Failed to load Shiller data", "historical": [], "current": {}, "forecast": [], "stats": {}}

    # Filter from 1965 onwards
    df = df[df["date"] >= "1965-01-01"].copy()

    required = ["sp500", "earnings", "cpi"]
    for col in required:
        if col not in df.columns:
            return {"error": f"Missing column: {col}", "historical": [], "current": {}, "forecast": [], "stats": {}}

    df = df.dropna(subset=["sp500", "cpi"])
    df["earnings"] = df["earnings"].ffill()
    df = df.dropna(subset=["earnings"])

    if len(df) < 24:
        return {"error": "Insufficient data", "historical": [], "current": {}, "forecast": [], "stats": {}}

    # ── 1. Trailing Earnings Yield (E/P) ──
    # Shiller earnings = trailing 12-month REPORTED (GAAP) earnings (annualized)
    df["ey"] = (df["earnings"] / df["sp500"]) * 100

    # ── 2. CPI YoY Inflation ──
    df["cpi_yoy"] = df["cpi"].pct_change(periods=12) * 100

    # ── 3. Real Earnings Yield = E/P - CPI YoY ──
    df["real_ey"] = df["ey"] - df["cpi_yoy"]

    # ── 4. CAPE Yield = 1/CAPE * 100 ──
    if "cape" in df.columns:
        df["cape_yield"] = 100.0 / df["cape"].replace(0, np.nan)
    else:
        df["cape_yield"] = np.nan

    # ── 5. 10-Year Average CPI Inflation (for ECY calculation) ──
    # ECY uses 10-year rolling average inflation, not spot CPI YoY
    df["avg_10y_inflation"] = df["cpi_yoy"].rolling(window=120, min_periods=60).mean()

    # ── 6. Excess CAPE Yield = CAPE Yield - Real 10Y Treasury ──
    # Real 10Y = Nominal 10Y - 10-year average inflation (Shiller's methodology)
    if "long_rate" in df.columns and "cape_yield" in df.columns:
        df["real_10y"] = df["long_rate"] - df["avg_10y_inflation"]
        df["ecy"] = df["cape_yield"] - df["real_10y"]
    else:
        df["ecy"] = np.nan

    # ── 7. Equity Risk Premium (Fed Model) = E/P - Nominal 10Y ──
    if "long_rate" in df.columns:
        df["erp"] = df["ey"] - df["long_rate"]
    else:
        df["erp"] = np.nan

    # Drop rows without real_ey (first 12 months have no CPI YoY)
    df = df.dropna(subset=["real_ey"]).reset_index(drop=True)

    # ── Live data point ──
    live = _get_live_data()
    live_row = None
    if live.get("spy_pe") and live["spy_pe"] > 0:
        current_ey = 100.0 / live["spy_pe"]
        last_cpi_yoy = df["cpi_yoy"].iloc[-1] if not df["cpi_yoy"].empty else 2.5
        current_real_ey = current_ey - last_cpi_yoy
        current_erp = (current_ey - live.get("treasury_10y", 4.0)) if live.get("treasury_10y") else None

        # ECY for current: use last available CAPE and 10Y avg inflation from dataset
        last_cape = df["cape"].iloc[-1] if "cape" in df.columns and pd.notna(df["cape"].iloc[-1]) else None
        last_avg_inflation = df["avg_10y_inflation"].iloc[-1] if pd.notna(df["avg_10y_inflation"].iloc[-1]) else 2.5
        current_ecy = None
        if last_cape and last_cape > 0 and live.get("treasury_10y"):
            cape_yield = 100.0 / last_cape
            real_10y = live["treasury_10y"] - last_avg_inflation
            current_ecy = cape_yield - real_10y

        live_row = {
            "date": pd.Timestamp.now().strftime("%Y-%m-%d"),
            "sp500": live.get("sp500_price") or live.get("spy_price"),
            "ey": round(current_ey, 2),
            "cpi_yoy": round(last_cpi_yoy, 2),
            "real_ey": round(current_real_ey, 2),
            "cape": round(last_cape, 1) if last_cape else None,
            "cape_yield": round(100.0 / last_cape, 2) if last_cape and last_cape > 0 else None,
            "ecy": round(current_ecy, 2) if current_ecy is not None else None,
            "erp": round(current_erp, 2) if current_erp is not None else None,
            "long_rate": live.get("treasury_10y"),
        }

    # ── Build historical array ──
    historical = []
    for _, row in df.iterrows():
        historical.append({
            "date": row["date"].strftime("%Y-%m-%d"),
            "sp500": round(row["sp500"], 2) if pd.notna(row["sp500"]) else None,
            "ey": round(row["ey"], 2) if pd.notna(row["ey"]) else None,
            "cpi_yoy": round(row["cpi_yoy"], 2) if pd.notna(row["cpi_yoy"]) else None,
            "real_ey": round(row["real_ey"], 2) if pd.notna(row["real_ey"]) else None,
            "cape": round(row["cape"], 1) if "cape" in df.columns and pd.notna(row.get("cape")) else None,
            "cape_yield": round(row["cape_yield"], 2) if pd.notna(row.get("cape_yield")) else None,
            "ecy": round(row["ecy"], 2) if pd.notna(row.get("ecy")) else None,
            "long_rate": round(row["long_rate"], 2) if pd.notna(row.get("long_rate")) else None,
            "erp": round(row["erp"], 2) if pd.notna(row.get("erp")) else None,
        })

    if live_row:
        historical.append(live_row)

    # ── Forecast (Holt's Linear Trend on last 12 months of real_ey) ──
    forecast = []
    try:
        recent = df["real_ey"].dropna().values[-12:]
        if len(recent) >= 6:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing
            model = ExponentialSmoothing(recent, trend="add", seasonal=None).fit(optimized=True)
            fc = model.forecast(steps=3)
            last_date = df["date"].iloc[-1]
            for i, val in enumerate(fc):
                forecast_date = last_date + pd.DateOffset(months=i + 1)
                forecast.append({
                    "date": forecast_date.strftime("%Y-%m-%d"),
                    "real_ey": round(float(val), 2),
                })
    except Exception as e:
        logger.warning("Forecast failed: %s", e)

    # ── REY Stats ──
    ey_series = df["real_ey"].dropna()
    current_val = live_row["real_ey"] if live_row else ey_series.iloc[-1]
    percentile = float((ey_series < current_val).mean() * 100)

    stats = {
        "avg": round(float(ey_series.mean()), 2),
        "median": round(float(ey_series.median()), 2),
        "min": round(float(ey_series.min()), 2),
        "max": round(float(ey_series.max()), 2),
        "current": round(current_val, 2),
        "current_percentile": round(percentile, 1),
        "positive_pct": round(float((ey_series > 0).mean() * 100), 1),
        "data_points": len(ey_series),
        "start_year": int(df["date"].iloc[0].year),
        "end_year": int(df["date"].iloc[-1].year),
    }

    # ── ECY Stats ──
    ecy_series = df["ecy"].dropna()
    ecy_current = live_row.get("ecy") if live_row else (ecy_series.iloc[-1] if len(ecy_series) else None)
    ecy_stats = {}
    if len(ecy_series) > 0 and ecy_current is not None:
        ecy_stats = {
            "avg": round(float(ecy_series.mean()), 2),
            "median": round(float(ecy_series.median()), 2),
            "min": round(float(ecy_series.min()), 2),
            "max": round(float(ecy_series.max()), 2),
            "current": round(ecy_current, 2),
            "current_percentile": round(float((ecy_series < ecy_current).mean() * 100), 1),
        }

    # ── Signal determination ──
    # Based on Yardeni/Brightwood thresholds with academic backing
    def _get_signal(rey: float) -> tuple[str, str]:
        if rey > 5:
            return "STRONG_BUY", "Real Earnings Yield above 5% — stocks are deeply undervalued vs inflation. Historically the best time to be fully invested. Every instance delivered strong 1-5 year returns."
        if rey > 3:
            return "BUY", "Real Earnings Yield above 3% (near 60-year average of {avg}%). Stocks are attractively valued. A good time to invest or stay invested.".format(avg=stats["avg"])
        if rey > 1.5:
            return "HOLD", "Real Earnings Yield positive but below average. Stocks are fairly valued. Stay invested but be selective — don't chase."
        if rey > 0:
            return "CAUTION", "Real Earnings Yield below 1.5% — historically associated with below-average forward returns. Consider reducing equity exposure or building cash."
        return "DANGER", "Real Earnings Yield is NEGATIVE — stocks are losing value vs inflation. This has preceded every major bear market (1987, 2000, 2008). Strongly consider reducing equity allocation."

    # ── Current snapshot ──
    current: dict[str, Any] = {}
    if live_row:
        signal, description = _get_signal(current_val)
        current = {
            "earnings_yield": live_row["ey"],
            "inflation": live_row["cpi_yoy"],
            "real_earnings_yield": live_row["real_ey"],
            "excess_cape_yield": live_row.get("ecy"),
            "equity_risk_premium": live_row.get("erp"),
            "treasury_10y": live.get("treasury_10y"),
            "sp500_price": live_row["sp500"],
            "spy_pe": live.get("spy_pe"),
            "cape": live_row.get("cape"),
            "signal": signal,
            "signal_description": description,
        }

    # ── Nasdaq relative valuation ──
    nasdaq: dict[str, Any] = {}
    if live.get("qqq_pe") and live.get("spy_pe") and live["spy_pe"] > 0:
        relative_pe = live["qqq_pe"] / live["spy_pe"]
        nasdaq = {
            "qqq_pe": round(live["qqq_pe"], 1),
            "spy_pe": round(live["spy_pe"], 1),
            "relative_pe": round(relative_pe, 2),
            "qqq_ey": round(100.0 / live["qqq_pe"], 2) if live["qqq_pe"] > 0 else None,
            "interpretation": (
                "Nasdaq trading at a significant premium to S&P 500 — growth expectations are high."
                if relative_pe > 1.3 else
                "Nasdaq and S&P 500 valuations are roughly in line."
                if relative_pe > 1.1 else
                "Nasdaq is cheaper than S&P 500 — unusual, may indicate growth skepticism."
            ),
        }

    result = {
        "historical": historical,
        "current": current,
        "forecast": forecast,
        "stats": stats,
        "ecy_stats": ecy_stats,
        "nasdaq": nasdaq,
    }

    _set_cached(cache_key, result)
    return result
