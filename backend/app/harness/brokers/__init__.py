"""Broker adapters. The runner depends only on the `Broker` protocol, so paper,
mock, and (later) live MCP brokers are interchangeable."""
from .base import Broker
from .mock import MockBroker

__all__ = ["Broker", "MockBroker", "get_broker"]


def get_broker(kind: str, user_id: str) -> Broker:
    """Factory. `mock` needs no credentials; `alpaca` needs paper keys in env."""
    if kind == "mock":
        return MockBroker(user_id)
    if kind == "alpaca":
        from .alpaca_paper import AlpacaPaperBroker  # imported lazily (optional dep)
        return AlpacaPaperBroker(user_id)
    if kind == "robinhood":
        from .mcp_broker import MCPBroker  # live Robinhood agentic MCP (needs /mcp auth)
        return MCPBroker(user_id)
    raise ValueError(f"Unknown broker kind: {kind!r}")
