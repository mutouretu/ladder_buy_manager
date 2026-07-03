from __future__ import annotations

import sqlite3
from math import floor
from io import StringIO

import pandas as pd

import db
import market_data
from models import GeneratedLevel


STATUS_LABELS = {
    "executed": "已买入",
    "triggered": "需处理",
    "pending": "等待",
    "unknown": "未更新价格",
}


def parse_optional_float(value: object) -> float | None:
    if value is None:
        return None
    if pd.isna(value):
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return float(value)


def level_status(current_price: float | None, level: sqlite3.Row | dict) -> str:
    if int(level["executed"]) == 1:
        return "executed"
    if current_price is None:
        return "unknown"
    if float(current_price) <= float(level["target_price"]):
        return "triggered"
    return "pending"


def overview_rows(active_only: bool = True) -> pd.DataFrame:
    rows: list[dict] = []
    instruments = db.list_instruments(active_only=active_only)
    for instrument in instruments:
        levels = db.list_levels(instrument["id"])
        current_price = instrument["current_price"]
        statuses = [level_status(current_price, level) for level in levels]
        executed_levels = [
            f"LV{level['level_index']}" for level in levels if int(level["executed"]) == 1
        ]
        invested_amount = sum(
            float(level["planned_amount"]) for level in levels if int(level["executed"]) == 1
        )
        triggered_levels = [
            f"LV{level['level_index']}"
            for level, status in zip(levels, statuses, strict=True)
            if status == "triggered"
        ]
        triggered_amount = sum(
            float(level["planned_amount"])
            for level, status in zip(levels, statuses, strict=True)
            if status == "triggered"
        )
        first_level = next(
            (level for level in levels if int(level["level_index"]) == 1),
            None,
        )
        if current_price is None:
            status = "未更新价格"
        elif triggered_levels:
            status = "需处理"
        else:
            status = "正常"

        rows.append(
            {
                "id": instrument["id"],
                "symbol": instrument["symbol"],
                "name": instrument["name"] or "",
                "category": instrument["category"] or "",
                "current_price": current_price,
                "updated_at": instrument["updated_at"] or "",
                "建仓价": first_level["target_price"] if first_level else None,
                "初始投资": first_level["planned_amount"] if first_level else None,
                "建仓时间": (first_level["executed_at"] or "") if first_level else "",
                "已买入档位数量": len(executed_levels),
                "总档位数量": len(levels),
                "加仓间隔": instrument["trigger_pct"],
                "已投": invested_amount,
                "已触发未买入档位": " / ".join(triggered_levels) if triggered_levels else "-",
                "已触发未买入金额合计": triggered_amount,
                "状态": status,
                "needs_action": bool(triggered_levels),
            }
        )
    return pd.DataFrame(rows)


def overview_totals(active_only: bool = True) -> dict:
    instruments = db.list_instruments(active_only=active_only)
    invested_amount = 0.0
    for instrument in instruments:
        for level in db.list_levels(instrument["id"]):
            if int(level["executed"]) == 1:
                invested_amount += float(level["planned_amount"])
    return {
        "instrument_count": len(instruments),
        "invested_amount": invested_amount,
    }


def refresh_instrument_price(instrument_id: int) -> market_data.Quote:
    instrument = db.get_instrument(instrument_id)
    if instrument is None:
        raise ValueError("标的不存在。")

    quote = market_data.fetch_latest_price(instrument["symbol"])
    with db.get_connection() as conn:
        conn.execute(
            """
            UPDATE instruments
            SET current_price = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (quote.price, quote.quote_date, int(instrument_id)),
        )
    return quote


def level_rows(instrument_id: int) -> pd.DataFrame:
    instrument = db.get_instrument(instrument_id)
    if instrument is None:
        return pd.DataFrame()
    levels = db.list_levels(instrument_id)
    rows = []
    for level in levels:
        status = level_status(instrument["current_price"], level)
        rows.append(
            {
                "id": level["id"],
                "LV": f"LV{level['level_index']}",
                "level_index": level["level_index"],
                "target_price": level["target_price"],
                "planned_amount": level["planned_amount"],
                "executed": bool(level["executed"]),
                "executed_at": level["executed_at"] or "",
                "computed_status": status,
                "状态": STATUS_LABELS[status],
            }
        )
    return pd.DataFrame(rows)


def instrument_summary(instrument_id: int) -> dict:
    instrument = db.get_instrument(instrument_id)
    if instrument is None:
        return {}
    levels = db.list_levels(instrument_id)
    triggered = [
        level
        for level in levels
        if level_status(instrument["current_price"], level) == "triggered"
    ]
    return {
        "instrument": instrument,
        "levels": levels,
        "triggered_levels": [f"LV{level['level_index']}" for level in triggered],
        "triggered_amount": sum(float(level["planned_amount"]) for level in triggered),
    }


def generate_levels(
    anchor_price: float,
    first_shares: int,
    trigger_pct: float,
    level_count: int,
) -> list[GeneratedLevel]:
    if anchor_price <= 0:
        raise ValueError("anchor_price 必须大于 0")
    if first_shares <= 0:
        raise ValueError("first_shares 必须大于 0")
    if not 0 <= trigger_pct < 1:
        raise ValueError("trigger_pct 必须在 0 到 1 之间")
    if level_count < 1:
        raise ValueError("level_count 必须至少为 1")

    levels: list[GeneratedLevel] = []
    price = float(anchor_price)
    target_amount = float(first_shares) * price
    for index in range(1, level_count + 1):
        if index == 1:
            shares = int(first_shares)
        else:
            shares = max(1, floor(target_amount / price + 0.5))
        amount = shares * price
        levels.append(
            GeneratedLevel(
                level_index=index,
                target_price=round(price, 4),
                planned_shares=shares,
                planned_amount=round(amount, 2),
            )
        )
        price *= 1 - trigger_pct
        target_amount /= 2
    return levels


def create_next_level(instrument_id: int) -> int:
    levels = sorted(db.list_levels(instrument_id), key=lambda level: int(level["level_index"]))
    if not levels:
        raise ValueError("该标的还没有 LV1，无法自动生成下一档。")

    last_level = levels[-1]
    next_index = int(last_level["level_index"]) + 1
    next_amount = round(float(last_level["planned_amount"]) / 2, 2)

    if len(levels) >= 2:
        previous_level = levels[-2]
        previous_price = float(previous_level["target_price"])
        last_price = float(last_level["target_price"])
        ratio = last_price / previous_price if previous_price > 0 else 1
        if ratio <= 0:
            ratio = 1
        next_price = round(last_price * ratio, 4)
    else:
        next_price = round(float(last_level["target_price"]), 4)

    return db.create_level(
        instrument_id=int(instrument_id),
        level_index=next_index,
        target_price=next_price,
        planned_amount=next_amount,
    )


def delete_lowest_level(instrument_id: int) -> int:
    levels = sorted(db.list_levels(instrument_id), key=lambda level: int(level["level_index"]))
    if len(levels) <= 1:
        raise ValueError("至少保留 LV1。")
    lowest_level = levels[-1]
    db.delete_level(int(lowest_level["id"]))
    return int(lowest_level["level_index"])


def create_plan_with_levels(
    symbol: str,
    name: str,
    category: str,
    levels: list[GeneratedLevel],
    trigger_pct: float | None = None,
) -> int:
    instrument_id = db.create_instrument(
        symbol=symbol,
        name=name,
        category=category,
        current_price=None,
        notes="",
        is_active=1,
        trigger_pct=trigger_pct,
    )
    try:
        for level in levels:
            db.create_level(
                instrument_id=instrument_id,
                level_index=level.level_index,
                target_price=level.target_price,
                planned_amount=level.planned_amount,
                executed=1 if int(level.level_index) == 1 else 0,
            )
    except Exception:
        db.deactivate_instrument(instrument_id)
        raise
    return instrument_id


def export_instruments_csv() -> str:
    rows = db.list_instruments(active_only=False)
    data = [dict(row) for row in rows]
    return pd.DataFrame(data).to_csv(index=False)


def export_levels_csv() -> str:
    rows = db.fetch_all(
        """
        SELECT
            levels.id,
            levels.instrument_id,
            instruments.symbol AS instrument_symbol,
            levels.level_index,
            levels.target_price,
            levels.planned_amount,
            levels.executed,
            levels.executed_at
        FROM levels
        JOIN instruments ON instruments.id = levels.instrument_id
        ORDER BY instruments.symbol ASC, levels.level_index ASC
        """
    )
    data = [dict(row) for row in rows]
    return pd.DataFrame(data).to_csv(index=False)


def import_instruments_csv(csv_text: str) -> int:
    frame = pd.read_csv(StringIO(csv_text))
    count = 0
    for row in frame.to_dict(orient="records"):
        symbol = str(row.get("symbol", "")).strip().upper()
        if not symbol:
            continue
        current_price = parse_optional_float(row.get("current_price"))
        trigger_pct = parse_optional_float(row.get("trigger_pct"))
        existing = db.get_instrument_by_symbol(symbol)
        if existing:
            db.update_instrument(
                instrument_id=existing["id"],
                symbol=symbol,
                name=str(row.get("name", "") or ""),
                category=str(row.get("category", "") or ""),
                current_price=current_price,
                notes=str(row.get("notes", "") or ""),
                is_active=int(row.get("is_active", 1) or 0),
                update_price_date=False,
                trigger_pct=trigger_pct,
            )
        else:
            db.create_instrument(
                symbol=symbol,
                name=str(row.get("name", "") or ""),
                category=str(row.get("category", "") or ""),
                current_price=current_price,
                notes=str(row.get("notes", "") or ""),
                is_active=int(row.get("is_active", 1) or 0),
                trigger_pct=trigger_pct,
            )
        count += 1
    return count


def import_levels_csv(csv_text: str) -> int:
    frame = pd.read_csv(StringIO(csv_text))
    count = 0
    for row in frame.to_dict(orient="records"):
        symbol = str(row.get("instrument_symbol", "") or "").strip().upper()
        instrument = db.get_instrument_by_symbol(symbol) if symbol else None
        if instrument is None and "instrument_id" in row:
            instrument = db.get_instrument(int(row["instrument_id"]))
        if instrument is None:
            continue

        level_index = int(row["level_index"])
        existing_levels = db.list_levels(instrument["id"])
        existing = next(
            (level for level in existing_levels if int(level["level_index"]) == level_index),
            None,
        )
        executed = int(row.get("executed", 0) or 0)
        if existing:
            db.update_level(
                level_id=existing["id"],
                level_index=level_index,
                target_price=float(row["target_price"]),
                planned_amount=float(row["planned_amount"]),
                executed=executed,
            )
        else:
            db.create_level(
                instrument_id=instrument["id"],
                level_index=level_index,
                target_price=float(row["target_price"]),
                planned_amount=float(row["planned_amount"]),
                executed=executed,
            )
        count += 1
    return count
