import logging
from typing import Any

import yfinance as yf

logger = logging.getLogger(__name__)


def pct_off_52wk_high(ticker: str) -> float | None:
    """Returns how far `ticker`'s last price sits below its 52-week high, as a
    negative percentage (e.g. -12.3 means 12.3% off the high; a value near 0
    means it's near the high). Returns None on any lookup failure -- yfinance
    scrapes Yahoo's undocumented endpoints, so a bad ticker, a delisted symbol,
    or a transient Yahoo error all raise different exception types. This must
    never break the weekly report over one ticker's price data.
    """
    try:
        fast_info = yf.Ticker(ticker).fast_info
        year_high = fast_info.year_high
        last_price = fast_info.last_price
        if not year_high:
            return None
        return (last_price - year_high) / year_high * 100
    except Exception:
        logger.warning("Could not fetch 52-week high for ticker %r", ticker, exc_info=True)
        return None


def attach_pct_off_high(recommendations: list[dict[str, Any]]) -> None:
    """Mutates each recommendation dict in place, adding a `pct_off_52wk_high`
    key (float, or None if the lookup failed or the ticker is a placeholder
    like "NONE"). Done here rather than in analyzer.py because Claude has no
    reliable access to live prices -- this is real market data, fetched
    per-ticker after the analysis is generated.
    """
    for rec in recommendations:
        ticker = rec.get("ticker", "")
        rec["pct_off_52wk_high"] = pct_off_52wk_high(ticker) if ticker and ticker != "NONE" else None
