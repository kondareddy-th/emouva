"""
Robinhood API service using robin_stocks.
Supports user-initiated login with device verification polling.
Session persisted via pickle for automatic reconnection.
"""

import logging
import os
import threading
import time
from typing import Any

import robin_stocks.robinhood as r

logger = logging.getLogger(__name__)

# ---------- state ----------
_logged_in = False
_login_lock = threading.Lock()
_cache: dict[str, tuple[float, Any]] = {}
CACHE_TTL = 30  # seconds
PICKLE_DIR = os.path.join(os.path.expanduser("~"), ".tokens")


# ---------- cache helpers ----------
def _get_cached(key: str, ttl: float = CACHE_TTL) -> Any | None:
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < ttl:
            return data
        del _cache[key]
    return None


def _set_cached(key: str, data: Any) -> None:
    _cache[key] = (time.time(), data)


def clear_cache() -> None:
    _cache.clear()


# ---------- auth ----------
# Capture the last raw API response so we can show the real error
_last_login_response: dict | None = None


def login(username: str, password: str, mfa_code: str | None = None) -> dict:
    """
    Initiate Robinhood login. Returns status dict:
    - {"status": "connected"} on success
    - {"status": "challenge", "message": "..."} if device approval needed
    - {"status": "failed", "message": "..."} on error
    """
    global _logged_in, _last_login_response
    with _login_lock:
        if _logged_in:
            return {"status": "connected"}

        # Monkey-patch request_post to capture raw Robinhood API responses
        # robin_stocks swallows errors and returns None, losing the actual message
        from robin_stocks.robinhood import authentication
        original_post = authentication.request_post
        _last_login_response = None
        captured = {"response": None}

        def capture_post(url, payload=None, timeout=16, json=False, jsonify_data=True):
            result = original_post(url, payload, timeout, json, jsonify_data)
            if result and isinstance(result, dict):
                captured["response"] = result
            return result
        authentication.request_post = capture_post

        try:
            result = r.login(
                username,
                password,
                store_session=True,
                expiresIn=86400,
                mfa_code=mfa_code,
            )
            if result and isinstance(result, dict) and "access_token" in result:
                _logged_in = True
                logger.info("Robinhood login successful")
                return {"status": "connected"}

            # robin_stocks may set login state even when it returns None
            from robin_stocks.robinhood.helper import LOGGED_IN
            if LOGGED_IN:
                _logged_in = True
                logger.info("Robinhood login successful (via login state)")
                return {"status": "connected"}

            # Check captured raw response for specific error details
            if captured["response"]:
                detail = captured["response"].get("detail", "")
                if detail:
                    logger.error("Robinhood login error: %s", detail)
                    return {"status": "failed", "message": detail}

            # Check result itself (some cases return dict with detail)
            if isinstance(result, dict):
                detail = result.get("detail", "")
                if detail:
                    logger.error("Robinhood login error: %s", detail)
                    return {"status": "failed", "message": detail}

            # If result is None and no error detail, a challenge was likely sent
            if result is None:
                return {
                    "status": "challenge",
                    "message": "Robinhood sent a verification request. Approve the push notification in your Robinhood app, then click Connect again. Or enter your MFA code if you use an authenticator app.",
                }

            logger.error("Robinhood login returned unexpected: %s", result)
            return {"status": "failed", "message": "Unexpected response from Robinhood"}

        except TimeoutError:
            from robin_stocks.robinhood.helper import LOGGED_IN
            if LOGGED_IN:
                _logged_in = True
                return {"status": "connected"}
            return {"status": "challenge", "message": "Device verification is pending. Approve the login in your Robinhood app and click Connect again."}

        except Exception as e:
            # One more check — login may have succeeded before the exception
            try:
                from robin_stocks.robinhood.helper import LOGGED_IN
                if LOGGED_IN:
                    _logged_in = True
                    logger.info("Robinhood login successful (despite exception: %s)", e)
                    return {"status": "connected"}
            except Exception:
                pass
            logger.exception("Robinhood login failed")
            return {"status": "failed", "message": str(e)}
        finally:
            # Restore original request_post
            authentication.request_post = original_post


def try_restore_session(username: str, password: str) -> bool:
    """Try to restore a saved session from pickle. Non-blocking."""
    global _logged_in
    pickle_path = os.path.join(PICKLE_DIR, "robinhood.pickle")
    if not os.path.isfile(pickle_path):
        return False

    with _login_lock:
        if _logged_in:
            return True
        try:
            result = r.login(
                username,
                password,
                store_session=True,
                expiresIn=86400,
            )
            if result and isinstance(result, dict) and "access_token" in result:
                _logged_in = True
                logger.info("Robinhood session restored from pickle")
                return True
        except Exception:
            logger.warning("Failed to restore Robinhood session")
    return False


def try_restore_from_pickle() -> bool:
    """Try to restore session from pickle without credentials.

    Loads the pickle, sets robin_stocks internal state, and verifies
    the token is still valid by making a simple API call.
    """
    import pickle

    global _logged_in
    pickle_path = os.path.join(PICKLE_DIR, "robinhood.pickle")
    if not os.path.isfile(pickle_path):
        return False

    with _login_lock:
        if _logged_in:
            return True
        try:
            with open(pickle_path, "rb") as f:
                pickle_data = pickle.load(f)

            # robin_stocks stores session data in helper module
            from robin_stocks.robinhood import helper

            if isinstance(pickle_data, dict) and "access_token" in pickle_data:
                # Set the access token in robin_stocks internal state
                helper.set_login_state(True)
                helper.update_session(
                    "Authorization", f"Bearer {pickle_data['access_token']}"
                )

                # Verify the token is still valid with a lightweight call
                profile = r.load_account_profile(info="url")
                if profile:
                    _logged_in = True
                    logger.info("Robinhood session restored from pickle (no credentials needed)")
                    return True
                else:
                    logger.warning("Pickle token expired, clearing login state")
                    helper.set_login_state(False)
        except Exception as e:
            logger.warning("Failed to restore from pickle: %s", e)
    return False


def disconnect() -> None:
    """Clear in-memory state but KEEP the pickle for session restoration on restart."""
    global _logged_in
    with _login_lock:
        try:
            r.logout()
        except Exception:
            pass
        _logged_in = False
        clear_cache()
        logger.info("Robinhood disconnected (session pickle preserved)")


def logout() -> None:
    """Full logout: clear in-memory state AND delete the session pickle."""
    global _logged_in
    with _login_lock:
        try:
            r.logout()
        except Exception:
            pass
        _logged_in = False
        clear_cache()
        pickle_path = os.path.join(PICKLE_DIR, "robinhood.pickle")
        if os.path.isfile(pickle_path):
            os.remove(pickle_path)
        logger.info("Robinhood logged out and session cleared")


_last_validated_at: float = 0.0
_SESSION_VALIDATION_TTL = 300  # re-validate every 5 minutes


def is_connected() -> bool:
    """Return True if Robinhood session is alive.

    Validates the session by making a lightweight API call at most every 5 min.
    If the call fails (e.g., token expired), clears login state so the UI reflects
    the real status instead of relying on a stale pickle.
    """
    global _logged_in, _last_validated_at
    if not _logged_in:
        return False

    now = time.time()
    if now - _last_validated_at < _SESSION_VALIDATION_TTL:
        return True

    try:
        # Cheap call — just fetches the account profile URL, no data
        profile = r.load_account_profile(info="url")
        if profile:
            _last_validated_at = now
            return True
        # Empty response = session expired
        logger.warning("Robinhood session validation failed — clearing login state")
        _logged_in = False
        return False
    except Exception as e:
        logger.warning("Robinhood session validation error: %s — clearing login state", e)
        _logged_in = False
        return False


# ---------- portfolio data ----------
def get_positions() -> list[dict]:
    """Get current holdings with enriched data."""
    if not _logged_in:
        return []

    cached = _get_cached("positions")
    if cached is not None:
        return cached

    try:
        holdings = r.build_holdings()
        if not holdings:
            return []

        symbols = list(holdings.keys())
        quotes = {}
        try:
            for q in r.get_quotes(symbols):
                if q and "symbol" in q:
                    quotes[q["symbol"]] = q
        except Exception:
            pass

        fundamentals = {}
        try:
            for f in r.get_fundamentals(symbols):
                if f and "symbol" in f:
                    fundamentals[f["symbol"]] = f
        except Exception:
            pass

        positions = []
        for symbol, h in holdings.items():
            quote = quotes.get(symbol, {})
            fund = fundamentals.get(symbol, {})
            sparkline = get_sparkline(symbol)

            positions.append({
                "symbol": symbol,
                "name": h.get("name", symbol),
                "shares": float(h.get("quantity", 0)),
                "avg_cost": float(h.get("average_buy_price", 0)),
                "current_price": float(h.get("price", 0)),
                "previous_close": float(quote.get("previous_close", h.get("price", 0))),
                "sector": fund.get("sector", "Unknown") or "Unknown",
                "sparkline": sparkline,
                "conviction": 3,
                "equity": float(h.get("equity", 0)),
                "percent_change": float(h.get("percent_change", 0)),
                "equity_change": float(h.get("equity_change", 0)),
            })

        positions.sort(key=lambda p: p["equity"], reverse=True)
        _set_cached("positions", positions)
        return positions

    except Exception:
        logger.exception("Failed to fetch Robinhood positions")
        return []


def get_account_info() -> dict:
    """Get account profile info including buying power."""
    if not _logged_in:
        return {}

    cached = _get_cached("account_info")
    if cached is not None:
        return cached

    try:
        profile = r.load_account_profile()
        info = {
            "buying_power": float(profile.get("buying_power", 0)),
            "cash": float(profile.get("cash", 0)),
            "portfolio_value": 0.0,
        }

        portfolio = r.load_portfolio_profile()
        if portfolio:
            info["portfolio_value"] = float(portfolio.get("equity", 0))
            info["total_gain"] = float(portfolio.get("equity", 0)) - float(
                portfolio.get("adjusted_equity_previous_close", portfolio.get("equity", 0))
            )

        _set_cached("account_info", info)
        return info

    except Exception:
        logger.exception("Failed to fetch account info")
        return {}


def get_watchlist(name: str = "Default") -> list[dict]:
    """Get watchlist with current quotes."""
    if not _logged_in:
        return []

    cache_key = f"watchlist_{name}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        watchlist_data = r.get_watchlist_by_name(name=name)
        if not watchlist_data:
            return []

        symbols = []
        for item in watchlist_data:
            instrument_url = item.get("instrument", "")
            if instrument_url:
                try:
                    inst = r.get_instrument_by_url(instrument_url)
                    if inst and "symbol" in inst:
                        symbols.append(inst["symbol"])
                except Exception:
                    pass

        if not symbols:
            return []

        quotes = r.get_quotes(symbols)
        items = []
        for q in quotes:
            if not q:
                continue
            symbol = q["symbol"]
            price = float(q.get("last_trade_price", 0))
            prev = float(q.get("previous_close", price))
            change_pct = ((price - prev) / prev * 100) if prev else 0

            items.append({
                "symbol": symbol,
                "name": q.get("simple_name", symbol) or symbol,
                "price": price,
                "change_pct": round(change_pct, 2),
                "sparkline": get_sparkline(symbol),
            })

        _set_cached(cache_key, items)
        return items

    except Exception:
        logger.exception("Failed to fetch watchlist")
        return []


def get_sparkline(symbol: str, span: str = "week", interval: str = "10minute") -> list[float]:
    """Get mini price history for sparkline chart, downsampled to ~20 points."""
    cache_key = f"sparkline_{symbol}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        historicals = r.get_stock_historicals(
            symbol, interval=interval, span=span,
        )
        if not historicals:
            return []

        prices = [float(h["close_price"]) for h in historicals if h and "close_price" in h]

        if len(prices) > 20:
            step = len(prices) / 20
            prices = [prices[int(i * step)] for i in range(20)]

        _set_cached(cache_key, prices)
        return prices

    except Exception:
        logger.exception("Failed to fetch sparkline for %s", symbol)
        return []


def get_portfolio_history(days: int = 90) -> list[dict]:
    """Build portfolio value history from individual stock historicals."""
    if not _logged_in:
        return []

    cache_key = f"portfolio_history_{days}"
    cache_ttl = 60 if days <= 1 else CACHE_TTL  # 1min for intraday, 30s default otherwise
    cached = _get_cached(cache_key, ttl=cache_ttl)
    if cached is not None:
        return cached

    try:
        positions = get_positions()
        if not positions:
            return []

        # Map days to robin_stocks span
        if days <= 1:
            span, interval = "day", "5minute"
        elif days <= 7:
            span, interval = "week", "day"
        elif days <= 30:
            span, interval = "month", "day"
        elif days <= 90:
            span, interval = "3month", "day"
        else:
            span, interval = "year", "day"

        # Fetch historicals for top positions (limit to 15 to avoid rate limits)
        top_positions = positions[:15]
        symbols = [p["symbol"] for p in top_positions]
        shares_map = {p["symbol"]: p["shares"] for p in top_positions}

        # Batch fetch historicals
        intraday = days <= 1
        all_historicals: dict[str, list] = {}
        for symbol in symbols:
            try:
                bounds = "extended" if intraday else "regular"
                hist = r.get_stock_historicals(symbol, interval=interval, span=span, bounds=bounds)
                if hist:
                    all_historicals[symbol] = hist
            except Exception:
                pass

        if not all_historicals:
            return []

        # Find common dates/timestamps across all stocks
        # Use the stock with the most data points as the date reference
        # For intraday (days<=1), keep full timestamp; for daily, use date only
        ref_symbol = max(all_historicals, key=lambda s: len(all_historicals[s]))
        ref_dates = [
            h["begins_at"] if intraday else h["begins_at"][:10]
            for h in all_historicals[ref_symbol]
        ]

        # Build price lookup: symbol -> {date_key -> close_price}
        price_lookup: dict[str, dict[str, float]] = {}
        for symbol, hist in all_historicals.items():
            price_lookup[symbol] = {
                (h["begins_at"] if intraday else h["begins_at"][:10]): float(h["close_price"])
                for h in hist
            }

        # Calculate portfolio value for each date
        # For stocks without data on a given date, use their current price
        history = []
        for date_str in ref_dates:
            total = 0.0
            for symbol in symbols:
                shares = shares_map[symbol]
                prices = price_lookup.get(symbol, {})
                price = prices.get(date_str)
                if price is None:
                    # Use last known price or current price
                    price = next(
                        (p["current_price"] for p in top_positions if p["symbol"] == symbol),
                        0,
                    )
                total += shares * price
            # Include remaining positions at current value
            remaining_value = sum(
                p["equity"] for p in positions[15:]
            )
            history.append({
                "date": date_str,
                "value": round(total + remaining_value, 2),
            })

        _set_cached(cache_key, history)
        return history

    except Exception:
        logger.exception("Failed to build portfolio history")
        return []


def get_portfolio_summary() -> dict:
    """Build portfolio summary from Robinhood data with computed risk score."""
    if not _logged_in:
        return {}

    positions = get_positions()
    account = get_account_info()

    if not positions and not account:
        return {}

    total_value = sum(p["equity"] for p in positions)
    total_cost = sum(p["shares"] * p["avg_cost"] for p in positions)
    daily_change = sum(p["equity_change"] for p in positions)
    total_gain = total_value - total_cost

    # Use computed risk score from the risk engine (cached for 5 min)
    risk_score = 50
    try:
        from app.services.risk import compute_risk_metrics
        risk_data = compute_risk_metrics(positions)
        risk_score = risk_data.get("score", 50)
    except Exception:
        logger.warning("Failed to compute risk score for summary")

    return {
        "total_value": round(total_value, 2),
        "daily_change": round(daily_change, 2),
        "daily_change_pct": round((daily_change / total_value * 100) if total_value else 0, 2),
        "total_gain": round(total_gain, 2),
        "total_gain_pct": round((total_gain / total_cost * 100) if total_cost else 0, 2),
        "buying_power": account.get("buying_power", 0),
        "risk_score": risk_score,
        "source": "robinhood",
    }


QUOTES_TTL = 5  # seconds


def get_quotes_fast(symbols: list[str]) -> list[dict]:
    """Lightweight batched quotes with 5-second cache."""
    if not _logged_in or not symbols:
        return []

    cache_key = "quotes_fast_" + ",".join(sorted(symbols))
    cached = _get_cached(cache_key, ttl=QUOTES_TTL)
    if cached is not None:
        return cached

    try:
        raw = r.get_quotes(symbols)
        results = []
        for q in raw:
            if not q or "symbol" not in q:
                continue
            price = float(q.get("last_trade_price") or 0)
            prev = float(q.get("previous_close") or price)
            change_pct = ((price - prev) / prev * 100) if prev else 0
            results.append({
                "symbol": q["symbol"],
                "price": round(price, 4),
                "previous_close": round(prev, 4),
                "change_pct": round(change_pct, 2),
            })
        _set_cached(cache_key, results)
        return results

    except Exception:
        logger.exception("Failed to fetch fast quotes")
        return []


# ---------- trading capabilities (new) ----------

def place_buy_order(
    symbol: str,
    amount_usd: float,
    order_type: str = "market",
    limit_price: float | None = None,
) -> dict:
    """Place a buy order by dollar amount (supports fractional shares).
    Returns dict with order_id, status, and order details."""
    if not _logged_in:
        return {"status": "failed", "error": "Not logged in to Robinhood"}

    try:
        if order_type == "limit" and limit_price:
            result = r.order_buy_limit(
                symbol,
                quantity=round(amount_usd / limit_price, 6),
                limitPrice=limit_price,
                timeInForce="gtc",
            )
        else:
            result = r.order_buy_fractional_by_price(
                symbol,
                amountInDollars=amount_usd,
                timeInForce="gtc",
            )

        if not result:
            return {"status": "failed", "error": "No response from Robinhood"}

        if isinstance(result, dict) and result.get("id"):
            logger.info("Buy order placed: %s $%.2f — order_id=%s", symbol, amount_usd, result["id"])
            return {
                "status": "submitted",
                "order_id": result["id"],
                "symbol": symbol,
                "amount_usd": amount_usd,
                "state": result.get("state", "unknown"),
                "price": result.get("price"),
                "quantity": result.get("quantity"),
            }

        logger.error("Buy order unexpected result: %s", result)
        return {"status": "failed", "error": str(result)}

    except Exception as e:
        logger.exception("Failed to place buy order for %s", symbol)
        return {"status": "failed", "error": str(e)}


def is_market_open() -> bool:
    """Check if NYSE is currently open for regular trading."""
    try:
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        hours = r.get_market_hours("XNYS", today)
        if not hours or not isinstance(hours, dict):
            return False

        if not hours.get("is_open", False):
            return False

        opens_at = hours.get("opens_at")
        closes_at = hours.get("closes_at")
        if not opens_at or not closes_at:
            return False

        now = datetime.now(timezone.utc)
        from datetime import datetime as dt
        open_time = dt.fromisoformat(opens_at.replace("Z", "+00:00"))
        close_time = dt.fromisoformat(closes_at.replace("Z", "+00:00"))
        return open_time <= now <= close_time

    except Exception:
        logger.exception("Failed to check market hours")
        return False


def get_open_orders() -> list[dict]:
    """Get all pending/open stock orders."""
    if not _logged_in:
        return []
    try:
        orders = r.get_all_open_stock_orders()
        results = []
        for order in (orders or []):
            results.append({
                "order_id": order.get("id"),
                "symbol": order.get("instrument_id"),  # needs resolution
                "side": order.get("side"),
                "quantity": order.get("quantity"),
                "price": order.get("price"),
                "type": order.get("type"),
                "state": order.get("state"),
                "created_at": order.get("created_at"),
            })
        return results
    except Exception:
        logger.exception("Failed to fetch open orders")
        return []


def get_order_status(order_id: str) -> dict:
    """Get the status of a specific order."""
    if not _logged_in:
        return {}
    try:
        order = r.get_stock_order_info(order_id)
        if order:
            return {
                "order_id": order.get("id"),
                "state": order.get("state"),
                "side": order.get("side"),
                "quantity": order.get("quantity"),
                "price": order.get("price"),
                "executions": order.get("executions", []),
            }
        return {}
    except Exception:
        logger.exception("Failed to get order status: %s", order_id)
        return {}


def get_fundamentals_data(symbols: list[str]) -> dict[str, dict]:
    """Get fundamental data (52-week high/low, P/E, etc.) for a list of symbols."""
    if not _logged_in:
        return {}
    try:
        raw = r.get_fundamentals(symbols)
        result = {}
        for i, f in enumerate(raw or []):
            if f:
                sym = symbols[i] if i < len(symbols) else "unknown"
                result[sym] = {
                    "high_52_weeks": float(f.get("high_52_weeks", 0) or 0),
                    "low_52_weeks": float(f.get("low_52_weeks", 0) or 0),
                    "pe_ratio": float(f.get("pe_ratio", 0) or 0),
                    "market_cap": float(f.get("market_cap", 0) or 0),
                    "dividend_yield": float(f.get("dividend_yield", 0) or 0),
                    "sector": f.get("sector", "Unknown"),
                }
        return result
    except Exception:
        logger.exception("Failed to fetch fundamentals")
        return {}
