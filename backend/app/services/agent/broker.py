"""Order execution, mode-aware. The agent proposes; the SafetyGate approves; this
places the order under the configured mode:

  dry_run — nothing placed (caller records intent).
  paper   — synthetic fill at market against the real book, recorded in our DB
            (no external brokerage, no keys — the P2 default for "paper money").
  alpaca  — real Alpaca paper brokerage (needs ALPACA_API_KEY_ID / _SECRET_KEY).
  live    — real Robinhood agentic account (P3, not yet implemented).

Returns a fill dict: {status, fill_price, filled_qty, filled_notional, broker_order_id, error}.
"""
from __future__ import annotations

import asyncio
import logging
import re

from app.config import settings

logger = logging.getLogger(__name__)

# Pre-trade `order_checks` alert types that are INFORMATIONAL disclosures, not hard
# blocks — Robinhood surfaces them on the individual/agentic account and the order still
# places (place_equity_order has no ack field; the tool guide says to surface, then place).
# We record them on the ledger for the audit trail and proceed. ANY other/unknown alert
# type still fails closed.
_ACK_ALERTS = {"EQUITY_SUITABILITY"}


async def execute(mode: str, symbol: str, side: str, qty: float, market_price: float,
                  *, token: str | None = None, account: str | None = None,
                  order_type: str = "market", limit_price: float | None = None,
                  ref_id: str | None = None) -> dict:
    if mode == "paper":
        # Synthetic fill at the current market price — logged in agent_orders as a
        # real (paper) fill so the user can watch the Partner trade their book on
        # paper money before going live.
        return {"status": "filled", "fill_price": round(market_price, 2), "filled_qty": qty,
                "filled_notional": round(market_price * qty, 2), "broker_order_id": None}
    if mode == "alpaca":
        return await asyncio.to_thread(_alpaca_place, symbol, side, qty)
    if mode == "live":
        # Fail-closed at every step. The engine has already verified assert_agentic
        # + the small-cap + approval gates before we get here.
        if settings.trading_halt:
            return {"status": "failed", "error": "trading halted (global kill switch)"}
        if not settings.live_execution_enabled:
            return {"status": "failed",
                    "error": "live execution disabled — set EMOUVA_LIVE_EXECUTION_ENABLED=true "
                             "only after confirming the place_equity_order arg schema"}
        if not (token and account):
            return {"status": "failed", "error": "live order missing token/account"}
        return await _robinhood_place(token, account, symbol, side, qty, order_type, limit_price, ref_id)
    return {"status": "proposed"}  # dry_run


def _order_args(account: str, symbol: str, side: str, qty: float, order_type: str,
                limit_price: float | None) -> dict:
    """Build the SHARED review/place args. Schema (verified 2026-07-07 via tools/list):
    all numerics are STRINGS; account must be agentic_allowed. NOTE: ref_id is a valid
    property on place_equity_order but NOT on review_equity_order, so it is added only at
    the place step (`_robinhood_place`), never here — sending it to review is rejected."""
    args = {
        "account_number": account,
        "symbol": symbol,
        "side": side,                       # "buy" | "sell"
        "type": order_type,                 # "market" | "limit"
        "quantity": str(qty),               # string per schema
        "time_in_force": "gfd",
        "market_hours": "regular_hours",
    }
    if order_type == "limit" and limit_price:
        args["limit_price"] = str(limit_price)
    return args


async def review_equity_order(token: str, account: str, symbol: str, side: str, qty: float,
                              order_type: str = "market", limit_price: float | None = None) -> dict:
    """Preview only — simulates the order, PLACES NOTHING. Returns the raw review
    (quote + pre-trade alerts). Used to verify the schema and pre-flight live orders."""
    from app.services.robinhood_mcp import RobinhoodMCP
    return await RobinhoodMCP(token).review_equity_order(
        _order_args(account, symbol, side, qty, order_type, limit_price))


async def _robinhood_place(token: str, account: str, symbol: str, side: str, qty: float,
                           order_type: str, limit_price: float | None, ref_id: str | None = None) -> dict:
    """Place a REAL order on the fenced agentic account via the Robinhood agentic
    MCP: preview (review_equity_order) then place (place_equity_order). Any tool
    error fails closed (order → failed, logged)."""
    from app.services.robinhood_mcp import RobinhoodMCP, MCPError

    args = _order_args(account, symbol, side, qty, order_type, limit_price)
    mcp = RobinhoodMCP(token)
    ack = None
    try:
        review = await mcp.review_equity_order(args)   # preview must succeed first
        rdata = review.get("data", review) if isinstance(review, dict) else {}
        checks = rdata.get("order_checks") or {}       # empty {} = no broker alerts
        disclosure = rdata.get("market_data_disclosure")
        alert = checks.get("alertType") if isinstance(checks, dict) else None
        # Some symbols (e.g. SNY and various ADRs) can't be traded FRACTIONALLY — retry once
        # with whole shares (floor), so a good idea isn't lost to a fractional quantity.
        if alert == "EQUITY_FRACTIONALLY_UNTRADABLE_ERROR_BUY" and qty != int(qty):
            whole = int(qty)   # floor
            if whole < 1:
                return {"status": "failed", "disclosure": disclosure,
                        "error": f"{symbol} isn't fractionally tradable and one whole share exceeds the size cap"}
            logger.info("%s not fractionally tradable — retrying %s→%d whole share(s)", symbol, qty, whole)
            qty = whole
            args = _order_args(account, symbol, side, qty, order_type, limit_price)
            review = await mcp.review_equity_order(args)
            rdata = review.get("data", review) if isinstance(review, dict) else {}
            checks = rdata.get("order_checks") or {}
            disclosure = rdata.get("market_data_disclosure")
            alert = checks.get("alertType") if isinstance(checks, dict) else None
        if checks and alert not in _ACK_ALERTS:
            # unknown / potentially blocking pre-trade check — fail closed, surface verbatim
            return {"status": "failed", "error": f"pre-trade checks: {checks}", "disclosure": disclosure}
        if checks:  # a known, informational disclosure — record it and proceed to place
            ack = checks
            logger.info("live order proceeding past disclosure %s for %s %s %s", alert, side, qty, symbol)
        place_args = dict(args)
        if ref_id:                                     # UUID idempotency — valid on place, not review
            place_args["ref_id"] = ref_id
        placed = await mcp.place_equity_order(place_args)
    except MCPError as e:
        msg = str(e)
        # Account-setup block: Robinhood requires the investor profile (investing goals)
        # to be completed for this account before further trades — surface it cleanly and
        # actionably (with the setup link) instead of the raw MCP error blob.
        if "investment_profile" in msg or "investor profile" in msg or "investing goals" in msg:
            m = re.search(r"https://applink\.robinhood\.com/investment_profile[^\s\"'}]+", msg)
            link = m.group(0) if m else None
            clean = ("Robinhood needs your investor profile completed for this account before "
                     "further trades (required by law after the first trade).")
            logger.warning("live order blocked — investor profile incomplete for %s", account)
            return {"status": "failed", "error": clean, "needs_investor_profile": True, "action_url": link}
        logger.warning("live order failed for %s %s %s: %s", side, qty, symbol, e)
        return {"status": "failed", "error": f"robinhood order error: {e}"}
    pdata = placed.get("data", placed) if isinstance(placed, dict) else {}
    # The order id/state live UNDER an "order" object (place_equity_order nests it);
    # fall back to the flat shape for other tools.
    obj = pdata.get("order") if isinstance(pdata.get("order"), dict) else pdata
    oid = obj.get("id") or obj.get("order_id") or obj.get("order_id_str") or pdata.get("id") or pdata.get("order_id")
    state = str(obj.get("state") or obj.get("status") or pdata.get("state") or pdata.get("status") or "").lower()
    if not oid:
        return {"status": "failed", "error": f"no order id in place result: {str(pdata)[:200]}",
                "disclosure": disclosure, "order_check_ack": ack}
    # 'unconfirmed'/'confirmed'/'queued' = accepted but not yet filled → 'placed';
    # real fill qty/price come from post-trade reconciliation (sync_from_robinhood).
    return {"status": "filled" if state == "filled" else "placed", "broker_order_id": oid,
            "fill_price": None, "filled_qty": None, "filled_notional": None,
            "raw_state": state, "disclosure": disclosure, "order_check_ack": ack}


def _alpaca_place(symbol: str, side: str, qty: float) -> dict:
    if not settings.alpaca_api_key_id or not settings.alpaca_api_secret_key:
        return {"status": "failed", "error": "Alpaca paper keys not set (ALPACA_API_KEY_ID / _SECRET_KEY)"}
    try:
        import time
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        client = TradingClient(settings.alpaca_api_key_id, settings.alpaca_api_secret_key, paper=True)
        order = client.submit_order(MarketOrderRequest(
            symbol=symbol, qty=qty,
            side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        ))
        for _ in range(10):  # market orders fill fast during RTH
            order = client.get_order_by_id(order.id)
            if str(order.status).lower().endswith("filled"):
                break
            time.sleep(0.5)
        fq = float(order.filled_qty or 0)
        fp = float(order.filled_avg_price or 0)
        return {"status": "filled" if fq else "placed", "fill_price": fp, "filled_qty": fq,
                "filled_notional": round(fp * fq, 2), "broker_order_id": str(order.id)}
    except Exception as e:
        logger.exception("Alpaca paper order failed")
        return {"status": "failed", "error": str(e)}
