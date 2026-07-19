

"""
Market data endpoints — yfinance enrichment (earnings, company info, news).
"""

from fastapi import APIRouter

from app.models.portfolio import EarningsResponse, CompanyInfo
from app.services import market_data

router = APIRouter(prefix="/api/market-data", tags=["market-data"])


@router.get("/{symbol}/earnings", response_model=EarningsResponse)
def earnings(symbol: str, years: int = 3):
    return market_data.get_earnings(symbol.upper(), years)


@router.get("/{symbol}/info", response_model=CompanyInfo)
def company_info(symbol: str):
    return market_data.get_company_info(symbol.upper())


@router.get("/{symbol}/news")
def news(symbol: str):
    return market_data.get_news(symbol.upper())
