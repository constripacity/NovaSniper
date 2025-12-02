"""Utilities for fetching product prices politely.

This module intentionally avoids any tactics that attempt to bypass
CAPTCHAs or anti-bot protections. The recommended approach is to use
official APIs:
- Amazon: Product Advertising API (requires registration and credentials)
- eBay: Browse API or Finding API (requires an application key)

The current implementation provides safe placeholders that can be
replaced with real API calls once credentials are configured. The helper
functions extract product identifiers from URLs without making network
calls.
"""

from __future__ import annotations

import logging
import re
from typing import Tuple

import requests

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
logger = logging.getLogger(__name__)


def extract_amazon_asin(value: str) -> str | None:
    """Extract an ASIN from a string or Amazon URL."""
    asin_pattern = re.compile(r"(?:dp|gp/product|product|ASIN)/([A-Z0-9]{10})", re.IGNORECASE)
    match = asin_pattern.search(value)
    if match:
        return match.group(1).upper()

    fallback_pattern = re.compile(r"([A-Z0-9]{10})")
    fallback_match = fallback_pattern.search(value)
    if fallback_match:
        return fallback_match.group(1).upper()
    return None


def extract_ebay_item_id(value: str) -> str | None:
    """Extract an eBay item ID from a string or URL."""
    item_pattern = re.compile(r"/itm/(?:.*?/)?(\d{9,})")
    match = item_pattern.search(value)
    if match:
        return match.group(1)

    query_pattern = re.compile(r"item=(\d{9,})")
    query_match = query_pattern.search(value)
    if query_match:
        return query_match.group(1)

    digits_pattern = re.compile(r"^(\d{9,})$")
    digits_match = digits_pattern.search(value)
    if digits_match:
        return digits_match.group(1)
    return None


def build_product_url(platform: str, product_id: str) -> str:
    if platform == "amazon":
        return f"https://www.amazon.com/dp/{product_id}"
    if platform == "ebay":
        return f"https://www.ebay.com/itm/{product_id}"
    raise ValueError("Unsupported platform")


def get_current_price(platform: str, product_id: str) -> Tuple[float | None, str | None]:
    """
    Retrieve the current price for a product.

    The implementation is deliberately conservative and avoids scraping or
    other brittle tactics. Replace the placeholder logic with official API
    calls once credentials are available:

    - Amazon Product Advertising API: use the SearchItems/GetItems
      endpoints and parse the price from the response.
    - eBay Browse or Finding APIs: use the "item_summary" or item details
      endpoints to fetch pricing.

    Returns (price, currency) or (None, None) if unavailable.
    """

    logger.info("Fetching price for %s item %s", platform, product_id)

    if platform == "ebay":
        api_price, api_currency = _fetch_ebay_price(product_id)
        if api_price is not None:
            return api_price, api_currency

    # Placeholder: deterministic pseudo-price for development/testing only.
    # This should be replaced with real API calls that respect platform ToS.
    seed_value = sum(ord(ch) for ch in product_id + platform)
    simulated_price = round((seed_value % 200) + 10 + (seed_value % 5) * 0.1, 2)
    simulated_currency = "USD"
    return simulated_price, simulated_currency


def _fetch_ebay_price(item_id: str) -> Tuple[float | None, str | None]:
    """Fetch price from the eBay Shopping API when credentials are provided.

    Uses the lightweight `GetSingleItem` endpoint which requires only the
    application ID (EBAY_APP_ID). If credentials are missing or a network/API
    error occurs, the function returns `(None, None)` so the caller can fall
    back to safe placeholder logic.
    """

    if not settings.ebay_app_id:
        logger.info("No EBAY_APP_ID provided; skipping live eBay price fetch")
        return None, None

    params = {
        "callname": "GetSingleItem",
        "responseencoding": "JSON",
        "appid": settings.ebay_app_id,
        "siteid": "0",
        "version": "967",
        "ItemID": item_id,
        "IncludeSelector": "Details,ItemSpecifics"
    }

    try:
        response = requests.get(
            "https://open.api.ebay.com/shopping",
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        item = data.get("Item")
        if not item:
            logger.warning("eBay response missing Item for %s", item_id)
            return None, None

        price_info = item.get("ConvertedCurrentPrice") or item.get("CurrentPrice")
        if not price_info:
            logger.warning("eBay response missing price data for %s", item_id)
            return None, None

        price_value = price_info.get("Value")
        currency = price_info.get("CurrencyID") or "USD"
        if price_value is None:
            logger.warning("eBay response price value is None for %s", item_id)
            return None, None

        return float(price_value), currency
    except requests.RequestException:
        logger.exception("Failed to fetch price from eBay for %s", item_id)
        return None, None
