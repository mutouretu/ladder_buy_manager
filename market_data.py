from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import certifi


class MarketDataError(RuntimeError):
    pass


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    quote_date: str
    provider: str
    name: str | None = None


@dataclass(frozen=True)
class HistoricalQuote:
    symbol: str
    price: float
    quote_at: str
    interval: str
    provider: str
    name: str | None = None


LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
MARKET_TIMEZONES = {
    "美股": "America/New_York",
    "A股": "Asia/Shanghai",
    "港股": "Asia/Hong_Kong",
    "加密": "UTC",
}
MARKET_CLOSE_TIMES = {
    "美股": time(16, 0),
    "A股": time(15, 0),
    "港股": time(16, 0),
}


def normalize_symbol(symbol: str, market: str | None = None) -> str:
    cleaned = symbol.strip().upper()
    if not cleaned:
        raise MarketDataError("标的代码不能为空。")
    market_name = (market or "").strip()
    if market_name == "加密":
        return normalize_crypto_symbol(cleaned)
    if market_name == "A股":
        return normalize_china_symbol(cleaned)
    return cleaned


def normalize_china_symbol(symbol: str) -> str:
    cleaned = symbol.replace(" ", "").upper()
    if cleaned.endswith(".SH"):
        return f"{cleaned[:-3]}.SS"
    if cleaned.endswith(".SS") or cleaned.endswith(".SZ") or cleaned.endswith(".BJ"):
        return cleaned
    if "." in cleaned:
        return cleaned
    if cleaned.startswith("920"):
        return f"{cleaned}.BJ"
    if cleaned.startswith(("5", "6", "9")):
        return f"{cleaned}.SS"
    if cleaned.startswith(("0", "1", "2", "3")):
        return f"{cleaned}.SZ"
    if cleaned.startswith(("4", "8")):
        return f"{cleaned}.BJ"
    return cleaned


def quote_name(result: dict) -> str | None:
    meta = result.get("meta") or {}
    name = meta.get("shortName") or meta.get("longName")
    cleaned = str(name or "").strip()
    return cleaned or None


def eastmoney_security_id(symbol: str) -> str:
    normalized_symbol = normalize_china_symbol(symbol)
    code, separator, suffix = normalized_symbol.partition(".")
    if not separator or suffix not in {"SS", "SZ", "BJ"}:
        raise MarketDataError(f"无法识别 A 股代码：{symbol}")
    market_id = "1" if suffix == "SS" else "0"
    return f"{market_id}.{code}"


def fetch_china_name(symbol: str, timeout: int = 10) -> str:
    query = urlencode(
        {
            "secid": eastmoney_security_id(symbol),
            "fields": "f57,f58",
        }
    )
    url = f"https://push2.eastmoney.com/api/qt/stock/get?{query}"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    context = ssl.create_default_context(cafile=certifi.where())
    try:
        with urlopen(request, timeout=timeout, context=context) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        raise MarketDataError(f"获取股票名称失败：{exc}") from exc
    data = payload.get("data") or {}
    name = str(data.get("f58") or "").strip()
    if not name or name == "-":
        raise MarketDataError(f"未找到 {symbol} 的股票名称。")
    return name


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


def fetch_chart_result(
    normalized_symbol: str,
    query_params: dict[str, str | int],
    timeout: int,
) -> dict:
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{quote(normalized_symbol)}?{urlencode(query_params)}"
    )
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
    return results[0]


def parse_local_datetime(value: str) -> datetime:
    cleaned = value.strip()
    for date_format in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, date_format).replace(tzinfo=LOCAL_TIMEZONE)
        except ValueError:
            continue
    raise MarketDataError("提出时间格式无效，应为 YYYY-MM-DD HH:MM。")


def close_points(result: dict) -> list[tuple[int, float]]:
    timestamps = result.get("timestamp") or []
    quote_rows = result.get("indicators", {}).get("quote") or []
    if not quote_rows:
        return []
    closes = quote_rows[0].get("close") or []
    return [
        (int(timestamp_value), float(close_value))
        for timestamp_value, close_value in zip(timestamps, closes)
        if timestamp_value is not None and close_value is not None
    ]


def exchange_timezone(result: dict, market: str | None) -> ZoneInfo:
    timezone_name = (result.get("meta") or {}).get("exchangeTimezoneName")
    if not timezone_name:
        timezone_name = MARKET_TIMEZONES.get((market or "").strip(), "UTC")
    try:
        return ZoneInfo(str(timezone_name))
    except Exception:
        return ZoneInfo("UTC")


def completed_daily_session_date(target: datetime, market: str | None) -> date:
    market_name = (market or "").strip()
    market_timezone = ZoneInfo(MARKET_TIMEZONES.get(market_name, "UTC"))
    market_time = target.astimezone(market_timezone)
    if market_name == "加密":
        return market_time.date() - timedelta(days=1)
    close_time = MARKET_CLOSE_TIMES.get(market_name, time(16, 0))
    if market_time.time() >= close_time:
        return market_time.date()
    return market_time.date() - timedelta(days=1)


def historical_intraday_quote(
    normalized_symbol: str,
    target: datetime,
    timeout: int,
) -> HistoricalQuote:
    interval_seconds = 5 * 60
    target_timestamp = int(target.timestamp())
    result = fetch_chart_result(
        normalized_symbol,
        {
            "period1": int((target - timedelta(days=7)).timestamp()),
            "period2": target_timestamp + 60,
            "interval": "5m",
            "events": "history",
            "includePrePost": "false",
        },
        timeout,
    )
    completed_cutoff = target_timestamp - interval_seconds
    eligible = [point for point in close_points(result) if point[0] <= completed_cutoff]
    if not eligible:
        raise MarketDataError("提出时间之前没有可用的 5 分钟行情。")
    bar_timestamp, close_value = eligible[-1]
    close_at = datetime.fromtimestamp(
        bar_timestamp + interval_seconds,
        timezone.utc,
    ).astimezone(LOCAL_TIMEZONE)
    return HistoricalQuote(
        symbol=normalized_symbol,
        price=close_value,
        quote_at=close_at.strftime("%Y-%m-%d %H:%M"),
        interval="5m",
        provider="Yahoo Finance",
        name=quote_name(result),
    )


def historical_daily_quote(
    normalized_symbol: str,
    target: datetime,
    market: str | None,
    timeout: int,
) -> HistoricalQuote:
    result = fetch_chart_result(
        normalized_symbol,
        {
            "period1": int((target - timedelta(days=30)).timestamp()),
            "period2": int((target + timedelta(days=2)).timestamp()),
            "interval": "1d",
            "events": "history",
        },
        timeout,
    )
    market_name = (market or "").strip()
    market_timezone = exchange_timezone(result, market)
    session_cutoff = completed_daily_session_date(target, market)
    eligible = [
        (timestamp_value, close_value)
        for timestamp_value, close_value in close_points(result)
        if datetime.fromtimestamp(timestamp_value, timezone.utc)
        .astimezone(market_timezone)
        .date()
        <= session_cutoff
    ]
    if not eligible:
        raise MarketDataError("提出时间之前没有可用的日线行情。")
    bar_timestamp, close_value = eligible[-1]
    session_date = datetime.fromtimestamp(bar_timestamp, timezone.utc).astimezone(
        market_timezone
    ).date()
    if market_name == "加密":
        close_at = datetime.combine(
            session_date + timedelta(days=1),
            time(0, 0),
            tzinfo=market_timezone,
        )
    else:
        close_at = datetime.combine(
            session_date,
            MARKET_CLOSE_TIMES.get(market_name, time(16, 0)),
            tzinfo=market_timezone,
        )
    return HistoricalQuote(
        symbol=normalized_symbol,
        price=close_value,
        quote_at=close_at.astimezone(LOCAL_TIMEZONE).strftime("%Y-%m-%d %H:%M"),
        interval="1d",
        provider="Yahoo Finance",
        name=quote_name(result),
    )


def fetch_latest_price(symbol: str, timeout: int = 10, market: str | None = None) -> Quote:
    normalized_symbol = normalize_symbol(symbol, market=market)
    result = fetch_chart_result(
        normalized_symbol,
        {"range": "5d", "interval": "1d"},
        timeout,
    )
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
        name=quote_name(result),
    )


def fetch_historical_price(
    symbol: str,
    at: str,
    timeout: int = 10,
    market: str | None = None,
) -> HistoricalQuote:
    normalized_symbol = normalize_symbol(symbol, market=market)
    target = parse_local_datetime(at)
    try:
        return historical_intraday_quote(normalized_symbol, target, timeout)
    except MarketDataError:
        return historical_daily_quote(
            normalized_symbol,
            target,
            market,
            timeout,
        )


def fetch_instrument_name(
    symbol: str,
    market: str | None = None,
    fallback: str | None = None,
    timeout: int = 10,
) -> str | None:
    fallback_name = str(fallback or "").strip() or None
    if (market or "").strip() == "A股":
        try:
            return fetch_china_name(symbol, timeout=timeout)
        except MarketDataError:
            return fallback_name
    if fallback_name:
        return fallback_name
    return fetch_latest_price(symbol, timeout=timeout, market=market).name
