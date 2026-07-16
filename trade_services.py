from __future__ import annotations

import sqlite3
from datetime import datetime
from math import floor

import pandas as pd

import db
import trade_db


STATUS_LABELS = {
    "watching": "观察中",
    "holding": "持仓中",
    "closed": "已清仓",
    "completed": "已完成",
}

BASE_CURRENCY = "USD"
MARKET_CURRENCIES = {
    "A股": "CNY",
    "美股": "USD",
    "港股": "HKD",
    "加密": "USD",
}
FX_TO_BASE = {
    "USD": 1.0,
    "CNY": 1 / 7.20,
    "HKD": 0.92 / 7.20,
}


IDEA_ROW_COLUMNS = [
    "id",
    "来源",
    "提出时间",
    "标的",
    "名称",
    "计划价",
    "当前价",
    "持仓股数",
    "卖出股数",
    "投入金额",
    "持仓成本",
    "均价",
    "买入价",
    "卖出价",
    "浮动盈亏",
    "浮动盈亏率",
    "已实现盈亏",
    "已实现盈亏率",
    "总收益",
    "总收益率",
    "状态",
]


def currency_for_market(market: str | None) -> str:
    return MARKET_CURRENCIES.get((market or "").strip(), BASE_CURRENCY)


def fx_rate_to_base(currency: str | None) -> float:
    return FX_TO_BASE.get((currency or "").strip(), 1.0)


def normalize_idea_at(idea_at: str | None) -> str:
    cleaned = (idea_at or "").strip()
    return cleaned or datetime.now().strftime("%Y-%m-%d %H:%M")


def display_idea_at(idea_at: str | None) -> str:
    cleaned = (idea_at or "").strip()
    if len(cleaned) == 10 and cleaned[4] == "-" and cleaned[7] == "-":
        return f"{cleaned} 00:00"
    return cleaned


def is_fractional_market(market: str | None) -> bool:
    return (market or "").strip() == "加密"


def is_fractional_shares_idea(idea_id: int) -> bool:
    idea = trade_db.get_idea(idea_id)
    if idea is None:
        return False
    source = trade_db.get_source(int(idea["source_id"]))
    return is_fractional_market(source["market"] if source is not None else None)


def normalize_status(status: str | None, position_shares: float, has_trade: bool) -> str:
    if status == "completed":
        return "已完成"
    if status == "closed":
        return "已清仓"
    if position_shares > 0 or status == "holding":
        return "持仓中"
    if status == "watching" or not has_trade:
        return "观察中"
    return "已清仓"


def source_rows() -> list[sqlite3.Row]:
    return trade_db.list_sources(active_only=True)


def get_source(source_id: int) -> sqlite3.Row | None:
    return trade_db.get_source(source_id)


def get_source_by_name(name: str) -> sqlite3.Row | None:
    return trade_db.get_source_by_name(name)


def create_source(name: str, market: str) -> int:
    cleaned_name = name.strip()
    if not cleaned_name:
        raise ValueError("项目名称不能为空。")
    existing = trade_db.get_source_by_name(cleaned_name)
    if existing is not None:
        raise ValueError("项目名称已存在。")
    return trade_db.create_source(cleaned_name, market)


def update_source(source_id: int, name: str, market: str) -> None:
    cleaned_name = name.strip()
    if not cleaned_name:
        raise ValueError("项目名称不能为空。")
    existing = trade_db.get_source_by_name(cleaned_name)
    if existing is not None and int(existing["id"]) != int(source_id):
        raise ValueError("项目名称已存在。")
    trade_db.update_source(source_id, cleaned_name, market)


def delete_source(source_id: int) -> None:
    trade_db.delete_source(source_id)


def get_idea(idea_id: int) -> sqlite3.Row | None:
    return trade_db.get_idea(idea_id)


def create_idea(
    source_id: int,
    symbol: str,
    name: str,
    idea_at: str,
    plan_price: float | None,
    current_price: float | None,
) -> int:
    cleaned_symbol = symbol.strip().upper()
    if not cleaned_symbol:
        raise ValueError("标的代码不能为空。")
    return trade_db.create_idea(
        source_id=source_id,
        symbol=cleaned_symbol,
        name=name,
        idea_at=normalize_idea_at(idea_at),
        plan_price=plan_price,
        current_price=current_price,
        status="watching",
    )


def update_idea(
    idea_id: int,
    symbol: str,
    name: str,
    idea_at: str,
    plan_price: float | None,
    current_price: float | None,
) -> None:
    cleaned_symbol = symbol.strip().upper()
    if not cleaned_symbol:
        raise ValueError("标的代码不能为空。")
    trade_db.update_idea(
        idea_id=idea_id,
        symbol=cleaned_symbol,
        name=name,
        idea_at=normalize_idea_at(idea_at),
        plan_price=plan_price,
        current_price=current_price,
    )


def delete_idea(idea_id: int) -> None:
    trade_db.delete_idea(idea_id)


def complete_idea(idea_id: int) -> None:
    trade_db.update_idea_status(idea_id, "completed")


def create_order(
    idea_id: int,
    side: str,
    trade_at: str,
    price: float,
    shares: float,
    fees: float = 0.0,
    ladder_level_id: int | None = None,
) -> int:
    normalized_side = side.strip().upper()
    if normalized_side not in {"BUY", "SELL"}:
        raise ValueError("交易方向必须是 BUY 或 SELL。")
    if float(price) <= 0:
        raise ValueError("交易价格必须大于 0。")
    if float(shares) <= 0:
        raise ValueError("股数必须大于 0。")
    order_id = trade_db.create_order(
        idea_id, normalized_side, trade_at, price, shares, fees, ladder_level_id
    )
    refresh_idea_status_from_orders(idea_id)
    return order_id


def get_order(order_id: int) -> sqlite3.Row | None:
    return trade_db.get_order(order_id)


def update_order(
    order_id: int,
    side: str,
    trade_at: str,
    price: float,
    shares: float,
    fees: float = 0.0,
) -> None:
    existing = trade_db.get_order(order_id)
    if existing is None:
        raise ValueError("交易记录不存在。")
    normalized_side = side.strip().upper()
    if normalized_side not in {"BUY", "SELL"}:
        raise ValueError("交易方向必须是 BUY 或 SELL。")
    if float(price) <= 0:
        raise ValueError("交易价格必须大于 0。")
    if float(shares) <= 0:
        raise ValueError("股数必须大于 0。")
    trade_db.update_order(
        order_id,
        normalized_side,
        trade_at,
        price,
        shares,
        fees,
        existing["ladder_level_id"],
    )
    refresh_idea_status_from_orders(int(existing["idea_id"]))
    sync_next_ladder_plan_price(int(existing["idea_id"]))


def delete_order(order_id: int) -> None:
    existing = trade_db.get_order(order_id)
    if existing is None:
        return
    idea_id = int(existing["idea_id"])
    trade_db.delete_order(order_id)
    refresh_idea_status_from_orders(idea_id)
    sync_next_ladder_plan_price(idea_id)


def generate_ladder_levels(
    anchor_price: float,
    first_shares: float,
    trigger_pct: float,
    level_count: int,
    allow_fractional_shares: bool = False,
) -> list[dict]:
    if float(anchor_price) <= 0:
        raise ValueError("首档价格必须大于 0。")
    if float(first_shares) <= 0:
        raise ValueError("首档股数必须大于 0。")
    if not allow_fractional_shares and float(first_shares) != int(float(first_shares)):
        raise ValueError("非加密市场的股数必须是整数。")
    if not 0 <= float(trigger_pct) < 1:
        raise ValueError("触发比例必须在 0 到 100% 之间。")
    if int(level_count) < 1:
        raise ValueError("档位数量至少为 1。")

    levels = []
    target_price = float(anchor_price)
    target_amount = float(anchor_price) * float(first_shares)
    for index in range(1, int(level_count) + 1):
        if index == 1:
            shares = float(first_shares)
        elif allow_fractional_shares:
            shares = round(target_amount / target_price, 8)
        else:
            shares = float(max(1, floor(target_amount / target_price + 0.5)))
        amount = target_price * shares
        levels.append(
            {
                "level_index": index,
                "target_price": round(target_price, 4),
                "planned_shares": shares if allow_fractional_shares else int(shares),
                "planned_amount": round(amount, 2),
            }
        )
        target_price *= 1 - float(trigger_pct)
        target_amount /= 2
    return levels


def create_or_replace_ladder_plan(
    idea_id: int,
    anchor_price: float,
    first_shares: float,
    trigger_pct: float,
    level_count: int,
) -> int:
    if trade_db.get_idea(idea_id) is None:
        raise ValueError("标的不存在。")
    allow_fractional_shares = is_fractional_shares_idea(idea_id)
    levels = generate_ladder_levels(
        anchor_price,
        first_shares,
        trigger_pct,
        level_count,
        allow_fractional_shares=allow_fractional_shares,
    )
    plan_id = trade_db.replace_ladder_plan(
        idea_id=idea_id,
        anchor_price=anchor_price,
        first_shares=first_shares,
        trigger_pct=trigger_pct,
        levels=levels,
    )
    sync_next_ladder_plan_price(idea_id)
    return plan_id


def get_ladder_plan_for_idea(idea_id: int) -> sqlite3.Row | None:
    return trade_db.get_ladder_plan_by_idea(idea_id)


def delete_ladder_plan(idea_id: int) -> None:
    trade_db.delete_ladder_plan(idea_id)
    trade_db.update_idea_plan_price(idea_id, None)


def sync_next_ladder_plan_price(idea_id: int) -> None:
    plan = trade_db.get_ladder_plan_by_idea(idea_id)
    if plan is None:
        return
    orders = trade_db.list_orders(idea_id)
    executed_level_ids = {
        int(order["ladder_level_id"])
        for order in orders
        if order["ladder_level_id"] is not None and order["side"] == "BUY"
    }
    next_level = next(
        (
            level
            for level in trade_db.list_ladder_levels(int(plan["id"]))
            if int(level["id"]) not in executed_level_ids
        ),
        None,
    )
    trade_db.update_idea_plan_price(
        idea_id,
        float(next_level["target_price"]) if next_level is not None else None,
    )


def sync_all_ladder_plan_prices() -> None:
    for idea in trade_db.list_ideas():
        if trade_db.get_ladder_plan_by_idea(int(idea["id"])) is not None:
            sync_next_ladder_plan_price(int(idea["id"]))


def ladder_status_rows(idea_id: int) -> list[dict]:
    idea = trade_db.get_idea(idea_id)
    if idea is None:
        return []
    plan = trade_db.get_ladder_plan_by_idea(idea_id)
    if plan is None:
        return []
    orders = trade_db.list_orders(idea_id)
    level_positions: dict[int, dict[str, float]] = {}
    for order in orders:
        if order["ladder_level_id"] is None:
            continue
        level_id = int(order["ladder_level_id"])
        level_positions.setdefault(level_id, {"buy": 0.0, "sell": 0.0})
        if order["side"] == "BUY":
            level_positions[level_id]["buy"] += float(order["shares"])
        elif order["side"] == "SELL":
            level_positions[level_id]["sell"] += float(order["shares"])
    rows = []
    for level in trade_db.list_ladder_levels(int(plan["id"])):
        position = level_positions.get(int(level["id"]), {"buy": 0.0, "sell": 0.0})
        open_shares = max(0.0, position["buy"] - position["sell"])
        if open_shares < 0.00000001:
            open_shares = 0.0
        if position["buy"] > 0 and open_shares == 0:
            status = "sold"
            status_label = "已卖出"
        elif position["buy"] > 0:
            status = "executed"
            status_label = "已买入"
        elif idea["current_price"] is None:
            status = "unknown"
            status_label = "未更新"
        elif float(idea["current_price"]) <= float(level["target_price"]):
            status = "triggered"
            status_label = "需处理"
        else:
            status = "pending"
            status_label = "等待"
        rows.append(
            {
                "id": level["id"],
                "plan_id": level["plan_id"],
                "level_index": level["level_index"],
                "target_price": level["target_price"],
                "planned_shares": level["planned_shares"],
                "planned_amount": level["planned_amount"],
                "bought_shares": position["buy"],
                "sold_shares": position["sell"],
                "open_shares": open_shares,
                "status": status,
                "状态": status_label,
            }
        )
    return rows


def execute_ladder_level(
    level_id: int,
    trade_at: str,
    price: float | None = None,
    shares: float | None = None,
    fees: float = 0.0,
) -> int:
    level = trade_db.get_ladder_level(level_id)
    if level is None:
        raise ValueError("分档不存在。")
    plan = trade_db.get_ladder_plan(int(level["plan_id"]))
    if plan is None:
        raise ValueError("分档计划不存在。")
    order_id = create_order(
        idea_id=int(plan["idea_id"]),
        side="BUY",
        trade_at=trade_at,
        price=float(price) if price is not None else float(level["target_price"]),
        shares=float(shares) if shares is not None else float(level["planned_shares"]),
        fees=fees,
        ladder_level_id=int(level_id),
    )
    sync_next_ladder_plan_price(int(plan["idea_id"]))
    return order_id


def sell_ladder_level(
    level_id: int,
    trade_at: str,
    price: float,
    shares: float | None = None,
    fees: float = 0.0,
) -> int:
    level = trade_db.get_ladder_level(level_id)
    if level is None:
        raise ValueError("分档不存在。")
    plan = trade_db.get_ladder_plan(int(level["plan_id"]))
    if plan is None:
        raise ValueError("分档计划不存在。")
    rows = ladder_status_rows(int(plan["idea_id"]))
    row = next((item for item in rows if int(item["id"]) == int(level_id)), None)
    if row is None:
        raise ValueError("分档不存在。")
    open_shares = float(row["open_shares"])
    if open_shares <= 0:
        raise ValueError("该档位没有可卖出的持仓。")
    sell_shares = open_shares if shares is None else float(shares)
    if sell_shares <= 0 or sell_shares - open_shares > 0.00000001:
        raise ValueError(f"卖出股数必须在 0 到 {open_shares:g} 之间。")
    order_id = create_order(
        idea_id=int(plan["idea_id"]),
        side="SELL",
        trade_at=trade_at,
        price=float(price),
        shares=sell_shares,
        fees=fees,
        ladder_level_id=int(level_id),
    )
    sync_next_ladder_plan_price(int(plan["idea_id"]))
    return order_id


def refresh_idea_status_from_orders(idea_id: int) -> None:
    idea = trade_db.get_idea(idea_id)
    if idea is None or idea["status"] == "completed":
        return
    restore_idea_from_archive(idea_id)


def restore_idea_from_archive(idea_id: int) -> None:
    idea = trade_db.get_idea(idea_id)
    if idea is None:
        return
    orders = trade_db.list_orders(idea_id)
    buy_shares = sum(float(order["shares"]) for order in orders if order["side"] == "BUY")
    if not orders:
        next_status = "watching"
    elif buy_shares > 0:
        next_status = "holding"
    else:
        next_status = "watching"
    trade_db.update_idea_status(idea_id, next_status)


def recover_idea_to_watchlist(idea_id: int) -> None:
    if trade_db.get_idea(idea_id) is None:
        return
    orders = trade_db.list_orders(idea_id)
    buy_shares = sum(float(order["shares"]) for order in orders if order["side"] == "BUY")
    next_status = "holding" if buy_shares > 0 else "watching"
    trade_db.update_idea_status(idea_id, next_status)


def idea_rows() -> pd.DataFrame:
    sources = {int(source["id"]): source for source in trade_db.list_sources(active_only=False)}
    orders_by_idea: dict[int, list[sqlite3.Row]] = {}
    for order in trade_db.list_orders():
        orders_by_idea.setdefault(int(order["idea_id"]), []).append(order)

    rows = []
    for idea in trade_db.list_ideas():
        source = sources.get(int(idea["source_id"]))
        if source is None:
            continue
        orders = orders_by_idea.get(int(idea["id"]), [])
        buy_shares = sum(float(order["shares"]) for order in orders if order["side"] == "BUY")
        sell_shares = sum(float(order["shares"]) for order in orders if order["side"] == "SELL")
        buy_amount = sum(
            float(order["price"]) * float(order["shares"]) + float(order["fees"])
            for order in orders
            if order["side"] == "BUY"
        )
        sell_amount = sum(
            float(order["price"]) * float(order["shares"]) - float(order["fees"])
            for order in orders
            if order["side"] == "SELL"
        )
        average_cost = buy_amount / buy_shares if buy_shares else None
        average_sell_price = sell_amount / sell_shares if sell_shares else None
        position_shares = buy_shares - sell_shares
        remaining_cost = (average_cost or 0) * position_shares
        realized_profit = (
            sell_amount - (average_cost or 0) * sell_shares
            if sell_shares and average_cost is not None
            else 0.0
        )
        current_price = idea["current_price"]
        floating_profit = (
            float(current_price) * position_shares - remaining_cost
            if current_price is not None and position_shares and average_cost is not None
            else 0.0
        )
        floating_pct = floating_profit / remaining_cost * 100 if remaining_cost > 0 else None
        realized_pct = (
            realized_profit / ((average_cost or 0) * sell_shares) * 100
            if sell_shares and average_cost
            else None
        )
        total_profit = floating_profit + realized_profit
        total_profit_pct = total_profit / buy_amount * 100 if buy_amount > 0 else None
        display_status = normalize_status(idea["status"], position_shares, has_trade=bool(orders))

        rows.append(
            {
                "id": idea["id"],
                "来源": source["name"],
                "提出时间": display_idea_at(idea["idea_at"]),
                "标的": idea["symbol"],
                "名称": idea["name"] or "",
                "计划价": idea["plan_price"],
                "当前价": current_price,
                "持仓股数": position_shares,
                "卖出股数": sell_shares,
                "投入金额": buy_amount,
                "持仓成本": remaining_cost,
                "均价": average_cost,
                "买入价": average_cost,
                "卖出价": average_sell_price,
                "浮动盈亏": floating_profit if position_shares else None,
                "浮动盈亏率": floating_pct,
                "已实现盈亏": realized_profit if sell_shares else None,
                "已实现盈亏率": realized_pct,
                "总收益": total_profit if buy_amount > 0 else None,
                "总收益率": total_profit_pct,
                "状态": display_status,
            }
        )
    return pd.DataFrame(rows, columns=IDEA_ROW_COLUMNS)


def source_summary() -> pd.DataFrame:
    rows = idea_rows()
    source_frame = pd.DataFrame([dict(source) for source in trade_db.list_sources(active_only=True)])
    stat_columns = [
        "来源",
        "标的数量",
        "持仓数量",
        "观察数量",
        "已清仓数量",
        "投入金额",
        "浮动盈亏",
        "已实现盈亏",
        "正收益数量",
        "平均收益率",
    ]
    if source_frame.empty:
        return pd.DataFrame(
            columns=[
                "id",
                "name",
                "market",
                "is_active",
                "币种",
                "汇率",
                *stat_columns[1:],
                "总收益",
                "投入金额折算",
                "浮动盈亏折算",
                "已实现盈亏折算",
                "总收益折算",
                "胜率",
                "单票平均收益",
                "单票平均收益率",
            ]
        )
    if rows.empty:
        stats = pd.DataFrame(columns=stat_columns)
    else:
        stats = (
            rows.groupby("来源", as_index=False)
            .agg(
                标的数量=("标的", "count"),
                持仓数量=("持仓股数", lambda values: int((values > 0).sum())),
                观察数量=("状态", lambda values: int((values == "观察中").sum())),
                已清仓数量=("状态", lambda values: int((values.isin(["已清仓", "已完成"])).sum())),
                投入金额=("投入金额", lambda values: values.fillna(0).sum()),
                浮动盈亏=("浮动盈亏", lambda values: values.fillna(0).sum()),
                已实现盈亏=("已实现盈亏", lambda values: values.fillna(0).sum()),
                正收益数量=("总收益", lambda values: int((values.fillna(0) > 0).sum())),
                平均收益率=("总收益率", "mean"),
            )
        )
    display = source_frame.merge(stats, left_on="name", right_on="来源", how="left")
    fill_values = {
        "标的数量": 0,
        "持仓数量": 0,
        "观察数量": 0,
        "已清仓数量": 0,
        "投入金额": 0.0,
        "浮动盈亏": 0.0,
        "已实现盈亏": 0.0,
        "正收益数量": 0,
    }
    display = display.fillna(fill_values)
    display["总收益"] = display["浮动盈亏"] + display["已实现盈亏"]
    display["币种"] = display["market"].map(currency_for_market)
    display["汇率"] = display["币种"].map(fx_rate_to_base)
    display["投入金额折算"] = display["投入金额"] * display["汇率"]
    display["浮动盈亏折算"] = display["浮动盈亏"] * display["汇率"]
    display["已实现盈亏折算"] = display["已实现盈亏"] * display["汇率"]
    display["总收益折算"] = display["总收益"] * display["汇率"]
    display["胜率"] = display.apply(
        lambda row: row["正收益数量"] / row["标的数量"] * 100
        if row["标的数量"]
        else None,
        axis=1,
    )
    display["单票平均收益"] = display.apply(
        lambda row: row["总收益"] / row["标的数量"] if row["标的数量"] else None,
        axis=1,
    )
    display["单票平均收益率"] = display["平均收益率"]
    return display


def order_rows_for_idea(idea_id: int) -> list[dict]:
    return [
        {
            "id": order["id"],
            "recommendation_id": order["idea_id"],
            "ladder_level_id": order["ladder_level_id"],
            "side": order["side"],
            "trade_at": order["trade_at"],
            "price": order["price"],
            "shares": order["shares"],
            "fees": order["fees"],
        }
        for order in trade_db.list_orders(idea_id)
    ]


def order_rows() -> list[dict]:
    return [
        {
            "id": order["id"],
            "recommendation_id": order["idea_id"],
            "ladder_level_id": order["ladder_level_id"],
            "side": order["side"],
            "trade_at": order["trade_at"],
            "price": order["price"],
            "shares": order["shares"],
            "fees": order["fees"],
        }
        for order in trade_db.list_orders()
    ]


def seed_demo_data_if_empty() -> None:
    if trade_db.list_sources(active_only=False):
        return

    source_1 = trade_db.create_source("北美成长股观察", "美股")
    source_2 = trade_db.create_source("港美策略周报", "港股")
    source_3 = trade_db.create_source("产业链朋友", "A股")

    nvda = trade_db.create_idea(source_1, "NVDA", "NVIDIA", "2026-06-18 09:30", 154.2, 162.35)
    crwd = trade_db.create_idea(source_1, "CRWD", "CrowdStrike", "2026-06-27 14:05", 398.5, 386.1)
    ita = trade_db.create_idea(source_2, "ITA", "iShares Aerospace & Defense ETF", "2026-07-01 10:15", 246.4, 245.11)
    trade_db.create_idea(source_2, "SG", "Sweetgreen", "2026-07-03 21:40", 9.8, 10.45)
    oln = trade_db.create_idea(source_3, "OLN", "Olin", "2026-07-05 11:20", 19.62, 20.74)

    demo_orders = [
        (nvda, "BUY", "2026-06-19", 155.1, 20, 0.0),
        (nvda, "BUY", "2026-06-24", 151.8, 10, 0.0),
        (nvda, "SELL", "2026-07-02", 165.0, 8, 0.0),
        (crwd, "BUY", "2026-06-28", 401.2, 8, 0.0),
        (crwd, "SELL", "2026-07-08", 386.1, 8, 0.0),
        (ita, "BUY", "2026-07-03", 246.41, 20, 0.0),
        (oln, "BUY", "2026-07-07", 19.62, 255, 0.0),
        (oln, "SELL", "2026-07-08", 21.1, 80, 0.0),
    ]
    for idea_id, side, trade_at, price, shares, fees in demo_orders:
        trade_db.create_order(idea_id, side, trade_at, price, shares, fees)
        refresh_idea_status_from_orders(idea_id)
