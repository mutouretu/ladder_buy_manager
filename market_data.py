from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import certifi


class MarketDataError(RuntimeError):
    pass


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    quote_date: str
    provider: str


def normalize_symbol(symbol: str, market: str | None = None) -> str:
    cleaned = symbol.strip().upper()
    if not cleaned:
        raise MarketDataError("标的代码不能为空。")
    if (market or "").strip() == "加密":
        return normalize_crypto_symbol(cleaned)
    return cleaned


def normalize_crypto_symbol(symbol: str) -> str:
    cleaned = symbol.replace(" ", "").upper()
    if "-" in cleaned:
        base, quote_symbol = cleaned.split("-", 1)
        return f"{base}-{crypto_quote_symbol(quote_symbol)}"
    if "/" in cleaned:
        base, quote_symbol = cleaned.split("/", 1)
        return f"{base}-{crypto_quote_symbol(quote_symbol)}"
    for quote_symbol in ("USDT", "USDC", "USD"):
        if cleaned.endswith(quote_symbol) and len(cleaned) > len(quote_symbol):
            return f"{cleaned[: -len(quote_symbol)]}-USD"
    return f"{cleaned}-USD"


def crypto_quote_symbol(symbol: str) -> str:
    cleaned = symbol.strip().upper()
    if cleaned in {"USDT", "USDC", "USD"}:
        return "USD"
    return cleaned or "USD"


def date_from_timestamp(timestamp: int | float | None, gmtoffset: int = 0) -> str:
    if not timestamp:
        return datetime.now().date().isoformat()
    adjusted = float(timestamp) + int(gmtoffset or 0)
    return datetime.fromtimestamp(adjusted, timezone.utc).date().isoformat()


def latest_close(result: dict) -> tuple[float, int | float | None]:
    timestamps = result.get("timestamp") or []
    quote_rows = result.get("indicators", {}).get("quote") or []
    if not quote_rows:
        raise MarketDataError("行情接口没有返回价格序列。")

    closes = quote_rows[0].get("close") or []
    for index in range(len(closes) - 1, -1, -1):
        close_value = closes[index]
        if close_value is not None:
            timestamp = timestamps[index] if index < len(timestamps) else None
            return float(close_value), timestamp
    raise MarketDataError("行情接口没有可用收盘价。")


def fetch_latest_price(symbol: str, timeout: int = 10, market: str | None = None) -> Quote:
    normalized_symbol = normalize_symbol(symbol, market=market)
    query = urlencode({"range": "5d", "interval": "1d"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(normalized_symbol)}?{query}"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    context = ssl.create_default_context(cafile=certifi.where())

    try:
        with urlopen(request, timeout=timeout, context=context) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        raise MarketDataError(f"获取行情失败：{exc}") from exc

    chart = payload.get("chart") or {}
    error = chart.get("error")
    if error:
        raise MarketDataError(error.get("description") or "行情接口返回错误。")

    results = chart.get("result") or []
    if not results:
        raise MarketDataError(f"未找到 {normalized_symbol} 的行情。")

    result = results[0]
    meta = result.get("meta") or {}
    gmtoffset = int(meta.get("gmtoffset") or 0)
    price_value = meta.get("regularMarketPrice")
    quote_timestamp = meta.get("regularMarketTime")
    if price_value is None:
        price_value, quote_timestamp = latest_close(result)

    try:
        price = float(price_value)
    except (TypeError, ValueError) as exc:
        raise MarketDataError(f"行情价格格式无效：{price_value}") from exc

    return Quote(
        symbol=normalized_symbol,
        price=price,
        quote_date=date_from_timestamp(quote_timestamp, gmtoffset),
        provider="Yahoo Finance",
    )
