from __future__ import annotations

import html
import sqlite3
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

import db
import market_data
import services
from models import GeneratedLevel


st.set_page_config(page_title="分档买入管理器", layout="wide")


def apply_global_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 100% !important;
            padding-left: 1.25rem !important;
            padding-right: 1.25rem !important;
            padding-top: 3.5rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def rerun() -> None:
    st.rerun()


def money(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{value:,.2f}"


def price(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{value:,.2f}"


def overview_row_style(needs_action: pd.Series):
    def style(row: pd.Series) -> list[str]:
        if bool(needs_action.loc[row.name]):
            return ["background-color: #ffe4e6; color: #111827; font-weight: 600"] * len(row)
        return [""] * len(row)

    return style


def level_border_style(position: int, total: int) -> str:
    left_border = "" if position == 0 else "border-left: 0;"
    radius = "0;"
    if position == 0:
        radius = "0.25rem 0 0 0.25rem;"
    elif position == total - 1:
        radius = "0 0.25rem 0.25rem 0;"
    return f"{left_border} border-radius: {radius}"


def level_cell_style(status: str, position: int, total: int) -> str:
    base = (
        "padding: 0.55rem 0.65rem; min-height: 2.45rem; "
        "border: 1px solid rgba(250, 250, 250, 0.18); "
        f"{level_border_style(position, total)}"
    )
    if status == "executed":
        return f"{base} color: #f9fafb; font-weight: 500;"
    if status == "triggered":
        return f"{base} background-color: #ffe4e6; color: #7f1d1d; font-weight: 700;"
    if status == "pending":
        return f"{base} background-color: #dcfce7; color: #14532d; font-weight: 600;"
    return f"{base} background-color: #f8fafc; color: #334155; font-weight: 500;"


def render_styled_cell(column, value: object, status: str, position: int, total: int) -> None:
    column.markdown(
        f"<div style='{level_cell_style(status, position, total)}'>{html.escape(str(value))}</div>",
        unsafe_allow_html=True,
    )


def render_header_cell(column, label: str, position: int, total: int) -> None:
    column.markdown(
        (
            "<div style='padding: 0.55rem 0.65rem; min-height: 2.45rem; "
            "border: 1px solid rgba(250, 250, 250, 0.18); "
            f"{level_border_style(position, total)} "
            "background-color: rgba(250, 250, 250, 0.06); font-weight: 700;'>"
            f"{html.escape(label)}</div>"
        ),
        unsafe_allow_html=True,
    )


def overview_cell_style(needs_action: bool, position: int, total: int) -> str:
    base = (
        "padding: 0.55rem 0.65rem; min-height: 2.45rem; "
        "border: 1px solid rgba(250, 250, 250, 0.18); "
        f"{level_border_style(position, total)}"
    )
    if needs_action:
        return f"{base} background-color: #ffe4e6; color: #111827; font-weight: 600;"
    return f"{base}"


def render_overview_cell(column, value: object, needs_action: bool, position: int, total: int) -> None:
    column.markdown(
        f"<div style='{overview_cell_style(needs_action, position, total)}'>{html.escape(str(value))}</div>",
        unsafe_allow_html=True,
    )


def query_param(name: str) -> str | None:
    value = st.query_params.get(name)
    if isinstance(value, list):
        return value[0] if value else None
    return value


def clear_query_params() -> None:
    st.query_params.clear()


def overview_action_url(action: str, instrument_id: int) -> str:
    return "?" + urlencode({"overview_action": action, "instrument_id": int(instrument_id)})


def overview_global_action_url(action: str) -> str:
    return "?" + urlencode({"overview_action": action})


def level_action_url(action: str, instrument_id: int, level_id: int) -> str:
    return "?" + urlencode(
        {
            "level_action": action,
            "instrument_id": int(instrument_id),
            "level_id": int(level_id),
        }
    )


def price_with_time(price_value: float | None, time_value: str | None) -> str:
    formatted_price = price(price_value)
    formatted_time = (time_value or "").strip()
    if formatted_price == "-":
        return "-"
    if not formatted_time:
        return formatted_price
    return f"{formatted_price}（{formatted_time}）"


def build_position_with_time(
    price_value: float | None, amount_value: float | None, time_value: str | None
) -> str:
    formatted_price = price(price_value)
    formatted_amount = money(amount_value)
    formatted_time = (time_value or "").strip()
    if formatted_price == "-":
        return "-"

    main_value = formatted_price
    if formatted_amount != "-":
        main_value = f"{formatted_price}/{formatted_amount}"
    if not formatted_time:
        return main_value
    return f"{main_value}（{formatted_time}）"


def planned_shares(planned_amount: float | None, target_price: float | None) -> int:
    if planned_amount is None or target_price is None:
        return 0
    if pd.isna(planned_amount) or pd.isna(target_price):
        return 0
    target = float(target_price)
    if target <= 0:
        return 0
    return max(0, int(round(float(planned_amount) / target)))


def amount_with_shares(planned_amount: float | None, target_price: float | None) -> str:
    amount_text = money(planned_amount)
    shares = planned_shares(planned_amount, target_price)
    if amount_text == "-":
        return "-"
    return f"{amount_text}/{shares}股"


def percent_signed(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):+.2f}%"


def signed_color(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "inherit"
    if float(value) > 0:
        return "#22c55e"
    if float(value) < 0:
        return "#f87171"
    return "inherit"


def render_colored_metric(column, label: str, value: str, color: str) -> None:
    label_color = color if color != "inherit" else "rgba(250, 250, 250, 0.6)"
    column.markdown(
        (
            "<div style='display: flex; flex-direction: column; gap: 0.15rem;'>"
            f"<div style='font-size: 0.875rem; color: {label_color}; "
            f"line-height: 1.25;'>{html.escape(label)}</div>"
            f"<div style='font-size: 1.75rem; line-height: 1.2; font-weight: 600; "
            f"color: {color};'>{html.escape(value)}</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def money_signed(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):+,.2f}"


def level_return_text(
    planned_amount: float | None,
    target_price: float | None,
    current_price: float | None,
    executed: bool,
) -> str:
    if not executed or current_price is None or pd.isna(current_price):
        return "-"
    if target_price is None or pd.isna(target_price):
        return "-"

    target = float(target_price)
    if target <= 0:
        return "-"

    shares = planned_shares(planned_amount, target_price)
    if shares <= 0:
        return "-"

    profit_value = (float(current_price) - target) * shares
    profit_pct = (float(current_price) - target) / target * 100
    return f"{money_signed(profit_value)}/{percent_signed(profit_pct)}"


def executed_position_stats(levels: list[sqlite3.Row], current_price: float | None) -> dict:
    invested_amount = 0.0
    invested_shares = 0
    for level in levels:
        if int(level["executed"]) != 1:
            continue
        amount = float(level["planned_amount"])
        shares = planned_shares(amount, level["target_price"])
        invested_amount += amount
        invested_shares += shares

    average_cost = invested_amount / invested_shares if invested_shares > 0 else None
    if (
        current_price is None
        or pd.isna(current_price)
        or average_cost is None
        or average_cost <= 0
    ):
        return {
            "invested_amount": invested_amount,
            "invested_shares": invested_shares,
            "average_cost": average_cost,
            "profit_value": None,
            "return_pct": None,
        }

    profit_value = (float(current_price) - average_cost) * invested_shares
    return_pct = (float(current_price) - average_cost) / average_cost * 100
    return {
        "invested_amount": invested_amount,
        "invested_shares": invested_shares,
        "average_cost": average_cost,
        "profit_value": profit_value,
        "return_pct": return_pct,
    }


def percent(value: float | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{float(value) * 100:.0f}%"


def level_count_text(executed_count: int, total_count: int, interval_pct: float | None) -> str:
    base = f"{int(executed_count)}/{int(total_count)}"
    formatted_interval = percent(interval_pct)
    if not formatted_interval:
        return base
    return f"{base}({formatted_interval})"


def colored_return_text(profit_value: float | None, return_pct: float | None) -> str:
    if profit_value is None or pd.isna(profit_value):
        return "-"
    css_class = "return-flat"
    if float(profit_value) > 0:
        css_class = "return-positive"
    elif float(profit_value) < 0:
        css_class = "return-negative"
    text = f"{money_signed(profit_value)}/{percent_signed(return_pct)}"
    return f"<span class='{css_class}'>{html.escape(text)}</span>"


def render_overview_table(frame: pd.DataFrame) -> None:
    labels = [
        "序号",
        "标的代码",
        "当前",
        "建仓",
        "档位",
        "已投",
        "收益",
        "操作",
    ]
    widths = [5, 10, 19, 18, 8, 10, 17, 13]

    header_cells = []
    for label in labels:
        if label == "操作":
            header_cells.append(
                "<th>"
                "<span class='overview-operation-header'>"
                "操作"
                f"<a class='overview-action' title='全部更新价格' "
                f"href='{overview_global_action_url('refresh_all')}' target='_self' rel='noreferrer'>↻</a>"
                "</span>"
                "</th>"
            )
        else:
            header_cells.append(f"<th>{html.escape(label)}</th>")
    header = "".join(header_cells)
    colgroup = "".join(f"<col style='width: {width}%'>" for width in widths)
    rows = []
    for row_index, row in frame.reset_index(drop=True).iterrows():
        instrument_id = int(row["id"])
        row_class = " class='needs-action'" if bool(row["needs_action"]) else ""
        cells = [
            row_index + 1,
            (
                f"<a class='overview-symbol' href='{overview_action_url('open', instrument_id)}' "
                "target='_self' rel='noreferrer'>"
                f"{html.escape(str(row['symbol']))}</a>"
            ),
            price(row["current_price"]),
            build_position_with_time(row["建仓价"], row["初始投资"], row["建仓时间"]),
            level_count_text(row["已买入档位数量"], row["总档位数量"], row["加仓间隔"]),
            money(row["已投"]),
            colored_return_text(row["收益值"], row["收益率"]),
            (
                "<span class='overview-actions'>"
                f"<a class='overview-action' title='从网络更新价格' "
                f"href='{overview_action_url('refresh', instrument_id)}' target='_self' rel='noreferrer'>↻</a>"
                f"<a class='overview-action' title='编辑' "
                f"href='{overview_action_url('edit', instrument_id)}' target='_self' rel='noreferrer'>✎</a>"
                f"<a class='overview-action danger' title='删除' "
                f"href='{overview_action_url('delete', instrument_id)}' target='_self' rel='noreferrer'>×</a>"
                "</span>"
            ),
        ]
        cell_html = "".join(
            f"<td>{cell}</td>"
            if isinstance(cell, str) and cell.startswith(("<a ", "<span "))
            else f"<td>{html.escape(str(cell))}</td>"
            for cell in cells
        )
        rows.append(f"<tr{row_class}>{cell_html}</tr>")

    st.markdown(
        f"""
        <style>
        .overview-table {{
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
            margin-top: 0.5rem;
            margin-bottom: 0.75rem;
            color: #f9fafb;
        }}
        .overview-table th,
        .overview-table td {{
            border: 1px solid rgba(250, 250, 250, 0.18);
            padding: 0.45rem 0.55rem;
            line-height: 1.25;
            vertical-align: middle;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .overview-table th {{
            background: rgba(250, 250, 250, 0.06);
            font-weight: 700;
        }}
        .overview-table tr.needs-action td {{
            background: #ffe4e6;
            color: #111827;
            font-weight: 600;
        }}
        .overview-symbol {{
            color: #bfdbfe;
            font-weight: 700;
            text-decoration: none;
        }}
        .overview-symbol:hover {{
            text-decoration: underline;
        }}
        .overview-table tr.needs-action .overview-symbol {{
            color: #111827;
        }}
        .overview-action {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.45rem;
            height: 1.45rem;
            border: 1px solid rgba(250, 250, 250, 0.28);
            border-radius: 0.2rem;
            color: inherit;
            font-weight: 800;
            text-decoration: none;
        }}
        .overview-actions {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.35rem;
            width: 100%;
        }}
        .overview-operation-header {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.35rem;
            width: 100%;
        }}
        .overview-action:hover {{
            background: rgba(250, 250, 250, 0.12);
        }}
        .overview-action.danger {{
            color: #fca5a5;
        }}
        .overview-table tr.needs-action .overview-action.danger {{
            color: #991b1b;
        }}
        .return-positive {{
            color: #22c55e;
            font-weight: 700;
        }}
        .return-negative {{
            color: #f87171;
            font-weight: 700;
        }}
        .return-flat {{
            color: inherit;
            font-weight: 700;
        }}
        .overview-table tr.needs-action .return-positive {{
            color: #166534;
        }}
        .overview-table tr.needs-action .return-negative {{
            color: #991b1b;
        }}
        </style>
        <table class="overview-table">
            <colgroup>{colgroup}</colgroup>
            <thead><tr>{header}</tr></thead>
            <tbody>{"".join(rows)}</tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )


def instrument_options(active_only: bool = True) -> list[sqlite3.Row]:
    return db.list_instruments(active_only=active_only)


def select_instrument(label: str, active_only: bool = True) -> sqlite3.Row | None:
    instruments = instrument_options(active_only=active_only)
    if not instruments:
        st.info("还没有标的，请先新增或快速创建分档计划。")
        return None

    option_by_label = {
        f"{row['symbol']} - {row['name'] or ''} (id={row['id']})": row for row in instruments
    }
    labels = list(option_by_label)
    selected_label = st.selectbox(label, labels)
    return option_by_label[selected_label]


def calculate_overview_totals(active_only: bool = True) -> dict:
    instruments = db.list_instruments(active_only=active_only)
    invested_amount = 0.0
    priced_invested_amount = 0.0
    profit_value = 0.0
    for instrument in instruments:
        current_price = instrument["current_price"]
        for level in db.list_levels(instrument["id"]):
            if int(level["executed"]) == 1:
                level_amount = float(level["planned_amount"])
                invested_amount += level_amount

                if current_price is None or pd.isna(current_price):
                    continue
                shares = planned_shares(level_amount, level["target_price"])
                if shares <= 0:
                    continue
                priced_invested_amount += level_amount
                profit_value += (float(current_price) - float(level["target_price"])) * shares

    profit_pct = (
        profit_value / priced_invested_amount * 100
        if priced_invested_amount > 0
        else None
    )
    return {
        "instrument_count": len(instruments),
        "invested_amount": invested_amount,
        "profit_value": profit_value if priced_invested_amount > 0 else None,
        "profit_pct": profit_pct,
    }


def update_level_execution_local(level_id: int, executed: int, executed_at: str | None) -> None:
    with db.get_connection() as conn:
        conn.execute(
            """
            UPDATE levels
            SET executed = ?,
                executed_at = ?
            WHERE id = ?
            """,
            (int(executed), executed_at, int(level_id)),
        )


def refresh_instrument_price_local(instrument_id: int) -> market_data.Quote:
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


def update_instrument_trigger_pct_local(instrument_id: int, trigger_pct: float | None) -> None:
    with db.get_connection() as conn:
        conn.execute(
            "UPDATE instruments SET trigger_pct = ? WHERE id = ?",
            (trigger_pct, int(instrument_id)),
        )


def infer_first_shares(level: sqlite3.Row | None) -> int | None:
    if level is None:
        return None
    target_price = float(level["target_price"])
    if target_price <= 0:
        return None
    return max(1, round(float(level["planned_amount"]) / target_price))


def infer_trigger_pct_from_levels(levels: list[sqlite3.Row]) -> float | None:
    first_level = next((level for level in levels if int(level["level_index"]) == 1), None)
    second_level = next((level for level in levels if int(level["level_index"]) == 2), None)
    if not first_level or not second_level:
        return None
    first_price = float(first_level["target_price"])
    if first_price <= 0:
        return None
    return 1 - float(second_level["target_price"]) / first_price


def has_add_on_execution(levels: list[sqlite3.Row]) -> bool:
    return any(int(level["level_index"]) > 1 and int(level["executed"]) == 1 for level in levels)


def create_plan_with_levels_local(
    symbol: str,
    name: str,
    category: str,
    levels: list[GeneratedLevel],
    trigger_pct: float | None,
) -> int:
    with db.get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO instruments (
                symbol, name, category, current_price, updated_at, trigger_pct, is_active, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (symbol.strip().upper(), name.strip(), category.strip(), None, None, trigger_pct, 1, ""),
        )
        instrument_id = int(cursor.lastrowid)
        for level in levels:
            executed = 1 if int(level.level_index) == 1 else 0
            executed_at = db.today_iso() if executed else None
            conn.execute(
                """
                INSERT INTO levels (
                    instrument_id, level_index, target_price, planned_amount, executed, executed_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    instrument_id,
                    int(level.level_index),
                    float(level.target_price),
                    float(level.planned_amount),
                    executed,
                    executed_at,
                ),
            )
    return instrument_id


def update_plan_with_levels_local(
    instrument_id: int,
    symbol: str,
    name: str,
    category: str,
    trigger_pct: float | None,
    build_time: str,
    levels: list[GeneratedLevel],
) -> None:
    existing_instrument = db.get_instrument(instrument_id)
    if existing_instrument is None:
        raise ValueError("标的不存在。")

    existing_levels = db.list_levels(instrument_id)
    if has_add_on_execution(existing_levels):
        raise ValueError("该标的已经有 LV2 及以后买入记录，不能重新生成分档计划。")

    existing_by_index = {int(level["level_index"]): level for level in existing_levels}
    new_indexes = {int(level.level_index) for level in levels}
    cleaned_build_time = build_time.strip()

    with db.get_connection() as conn:
        conn.execute(
            """
            UPDATE instruments
            SET symbol = ?,
                name = ?,
                category = ?,
                trigger_pct = ?
            WHERE id = ?
            """,
            (symbol.strip().upper(), name.strip(), category.strip(), trigger_pct, int(instrument_id)),
        )

        for level in existing_levels:
            if int(level["level_index"]) not in new_indexes:
                conn.execute("DELETE FROM levels WHERE id = ?", (int(level["id"]),))

        for level in levels:
            level_index = int(level.level_index)
            existing_level = existing_by_index.get(level_index)
            if level_index == 1:
                executed = 1 if cleaned_build_time else 0
                executed_at = cleaned_build_time or None
            elif existing_level:
                executed = int(existing_level["executed"])
                executed_at = existing_level["executed_at"]
            else:
                executed = 0
                executed_at = None

            if existing_level:
                conn.execute(
                    """
                    UPDATE levels
                    SET target_price = ?,
                        planned_amount = ?,
                        executed = ?,
                        executed_at = ?
                    WHERE id = ?
                    """,
                    (
                        float(level.target_price),
                        float(level.planned_amount),
                        executed,
                        executed_at,
                        int(existing_level["id"]),
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO levels (
                        instrument_id, level_index, target_price, planned_amount, executed, executed_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(instrument_id),
                        level_index,
                        float(level.target_price),
                        float(level.planned_amount),
                        executed,
                        executed_at,
                    ),
                )


def update_instrument_basic_local(
    instrument_id: int,
    symbol: str,
    name: str,
    category: str,
    build_time: str,
) -> None:
    levels = db.list_levels(instrument_id)
    if has_add_on_execution(levels) and not build_time.strip():
        raise ValueError("该标的已有加仓记录，建仓时间不能为空。")

    with db.get_connection() as conn:
        conn.execute(
            """
            UPDATE instruments
            SET symbol = ?,
                name = ?,
                category = ?
            WHERE id = ?
            """,
            (symbol.strip().upper(), name.strip(), category.strip(), int(instrument_id)),
        )

        first_level = next((level for level in levels if int(level["level_index"]) == 1), None)
        if first_level:
            cleaned_time = build_time.strip()
            conn.execute(
                """
                UPDATE levels
                SET executed = ?,
                    executed_at = ?
                WHERE id = ?
                """,
                (1 if cleaned_time else 0, cleaned_time or None, int(first_level["id"])),
            )


def refresh_all_prices_local() -> tuple[list[market_data.Quote], list[str]]:
    quotes: list[market_data.Quote] = []
    errors: list[str] = []
    for instrument in db.list_instruments(active_only=True):
        try:
            quotes.append(refresh_instrument_price_local(int(instrument["id"])))
        except Exception as exc:
            errors.append(f"{instrument['symbol']}：{exc}")
    return quotes, errors


@st.dialog("编辑标的")
def edit_instrument_dialog(instrument_id: int) -> None:
    instrument = db.get_instrument(instrument_id)
    if instrument is None:
        st.warning("标的不存在，可能已经被删除。")
        return

    levels = db.list_levels(int(instrument_id))
    has_add_on = has_add_on_execution(levels)
    first_level = next(
        (level for level in levels if int(level["level_index"]) == 1),
        None,
    )
    first_shares = infer_first_shares(first_level)
    trigger_pct = instrument["trigger_pct"]
    if trigger_pct is None:
        trigger_pct = infer_trigger_pct_from_levels(levels)

    if has_add_on:
        st.warning("该标的已经有 LV2 及以后买入记录，只能修改基本信息，不能重新生成分档计划。")

    with st.form(f"edit_instrument_dialog_{instrument_id}"):
        symbol = st.text_input("标的代码", value=instrument["symbol"])
        name = st.text_input("名称", value=instrument["name"] or "")
        category = st.text_input("分类", value=instrument["category"] or "")
        anchor_price = st.number_input(
            "首档触发价",
            min_value=0.0,
            value=float(first_level["target_price"]) if first_level else None,
            step=0.01,
            format="%.4f",
            placeholder="必填",
            disabled=has_add_on,
        )
        first_shares_input = st.number_input(
            "首档股数",
            min_value=1,
            value=int(first_shares) if first_shares else None,
            step=1,
            placeholder="必填",
            disabled=has_add_on,
        )
        trigger_pct_percent = st.number_input(
            "触发比例（%）",
            min_value=0.0,
            max_value=99.0,
            value=round(float(trigger_pct) * 100, 2) if trigger_pct is not None else None,
            step=1.0,
            format="%.2f",
            placeholder="必填，例如 10",
            disabled=has_add_on,
        )
        level_count = st.number_input(
            "档位数量",
            min_value=1,
            max_value=50,
            value=max(1, len(levels)),
            step=1,
            disabled=has_add_on,
        )
        build_time = st.text_input(
            "建仓时间",
            value=(first_level["executed_at"] or "") if first_level else "",
            placeholder="YYYY-MM-DD",
        )
        save_basic = st.form_submit_button("保存基本信息")
        preview = st.form_submit_button("生成预览", disabled=has_add_on)

    preview_key = f"edit_generated_levels_{instrument_id}"
    meta_key = f"edit_generated_meta_{instrument_id}"
    if save_basic:
        try:
            normalized_symbol = symbol.strip().upper()
            if not normalized_symbol:
                raise ValueError("标的代码不能为空。")
            update_instrument_basic_local(
                instrument_id=int(instrument_id),
                symbol=normalized_symbol,
                name=name,
                category=category,
                build_time=build_time,
            )
            st.session_state.pop(preview_key, None)
            st.session_state.pop(meta_key, None)
            clear_query_params()
            rerun()
        except sqlite3.IntegrityError:
            st.error("标的代码已存在。")
        except ValueError as exc:
            st.error(str(exc))

    if preview:
        try:
            if has_add_on:
                raise ValueError("该标的已经有 LV2 及以后买入记录，不能重新生成分档计划。")
            normalized_symbol = symbol.strip().upper()
            if not normalized_symbol:
                raise ValueError("标的代码不能为空。")
            if anchor_price is None:
                raise ValueError("首档触发价不能为空。")
            if float(anchor_price) <= 0:
                raise ValueError("首档触发价必须大于 0。")
            if first_shares_input is None:
                raise ValueError("首档股数不能为空。")
            if int(first_shares_input) <= 0:
                raise ValueError("首档股数必须大于 0。")
            if trigger_pct_percent is None:
                raise ValueError("触发比例不能为空。")
            computed_trigger_pct = float(trigger_pct_percent) / 100
            generated_levels = services.generate_levels(
                anchor_price=float(anchor_price),
                first_shares=int(first_shares_input),
                trigger_pct=computed_trigger_pct,
                level_count=int(level_count),
            )
            st.session_state[preview_key] = generated_levels
            st.session_state[meta_key] = {
                "symbol": normalized_symbol,
                "name": name.strip(),
                "category": category.strip(),
                "trigger_pct": computed_trigger_pct,
                "build_time": build_time.strip(),
            }
        except ValueError as exc:
            st.error(str(exc))

    generated = st.session_state.get(preview_key, [])
    if generated and not has_add_on:
        st.data_editor(
            pd.DataFrame([level.__dict__ for level in generated]),
            width="stretch",
            hide_index=True,
            disabled=True,
            column_config={
                "level_index": st.column_config.NumberColumn("LV 编号"),
                "target_price": st.column_config.NumberColumn("触发价格", format="%.4f"),
                "planned_shares": st.column_config.NumberColumn("计划股数"),
                "planned_amount": st.column_config.NumberColumn("计划投入", format="%.2f"),
            },
        )
        if st.button("保存", type="primary", key=f"save_edit_plan_{instrument_id}"):
            meta = st.session_state.get(meta_key, {})
            try:
                update_plan_with_levels_local(
                    instrument_id=int(instrument_id),
                    symbol=meta["symbol"],
                    name=meta.get("name", ""),
                    category=meta.get("category", ""),
                    trigger_pct=meta.get("trigger_pct"),
                    build_time=meta.get("build_time", ""),
                    levels=generated,
                )
                st.session_state.pop(preview_key, None)
                st.session_state.pop(meta_key, None)
                clear_query_params()
                rerun()
            except sqlite3.IntegrityError:
                st.error("标的代码已存在，或 LV 编号重复。")
            except ValueError as exc:
                st.error(str(exc))

    if st.button("取消"):
        st.session_state.pop(preview_key, None)
        st.session_state.pop(meta_key, None)
        clear_query_params()
        rerun()


@st.dialog("确认删除")
def delete_instrument_dialog(instrument_id: int) -> None:
    instrument = db.get_instrument(instrument_id)
    if instrument is None:
        st.warning("标的不存在，可能已经被删除。")
        return

    st.write(f"确定删除 {instrument['symbol']} 吗？")
    left, right = st.columns(2)
    if left.button("是", type="primary", width="stretch"):
        db.delete_instrument(int(instrument_id))
        if st.session_state.get("selected_instrument_id") == instrument_id:
            st.session_state.pop("selected_instrument_id", None)
        clear_query_params()
        rerun()
    if right.button("否", width="stretch"):
        clear_query_params()
        rerun()


@st.dialog("新建分档计划")
def quick_create_dialog() -> None:
    with st.form("quick_create_dialog_form"):
        symbol = st.text_input("标的代码", placeholder="例如 CAT")
        name = st.text_input("名称")
        category = st.text_input("分类")
        anchor_price = st.number_input(
            "首档触发价",
            min_value=0.0,
            value=None,
            step=0.01,
            format="%.4f",
            placeholder="必填",
        )
        first_shares = st.number_input(
            "首档股数",
            min_value=1,
            value=None,
            step=1,
            placeholder="必填",
        )
        trigger_pct_percent = st.number_input(
            "触发比例（%）",
            min_value=0.0,
            max_value=99.0,
            step=1.0,
            value=None,
            format="%.2f",
            placeholder="必填，例如 10",
        )
        level_count = st.number_input("档位数量", min_value=1, max_value=50, step=1, value=5)
        preview = st.form_submit_button("生成预览")

    if preview:
        try:
            if not symbol.strip():
                raise ValueError("标的代码不能为空。")
            if anchor_price is None:
                raise ValueError("首档触发价不能为空。")
            if float(anchor_price) <= 0:
                raise ValueError("首档触发价必须大于 0。")
            if first_shares is None:
                raise ValueError("首档股数不能为空。")
            if int(first_shares) <= 0:
                raise ValueError("首档股数必须大于 0。")
            if trigger_pct_percent is None:
                raise ValueError("触发比例不能为空。")
            if int(level_count) < 1:
                raise ValueError("档位数量必须至少为 1。")
            trigger_pct = float(trigger_pct_percent) / 100
            st.session_state["dialog_generated_levels"] = services.generate_levels(
                anchor_price=float(anchor_price),
                first_shares=int(first_shares),
                trigger_pct=trigger_pct,
                level_count=int(level_count),
            )
            st.session_state["dialog_generated_meta"] = {
                "symbol": symbol.strip().upper(),
                "name": name.strip(),
                "category": category.strip(),
                "trigger_pct": trigger_pct,
            }
        except ValueError as exc:
            st.error(str(exc))

    generated = st.session_state.get("dialog_generated_levels", [])
    if generated:
        frame = pd.DataFrame([level.__dict__ for level in generated])
        if "planned_shares" not in frame.columns:
            frame["planned_shares"] = (
                frame["planned_amount"] / frame["target_price"]
            ).round().astype(int)
        edited = st.data_editor(
            frame,
            width="stretch",
            hide_index=True,
            column_config={
                "level_index": st.column_config.NumberColumn("LV 编号", min_value=1, step=1),
                "target_price": st.column_config.NumberColumn("触发价格", min_value=0.0, format="%.4f"),
                "planned_shares": st.column_config.NumberColumn("计划股数", min_value=1, step=1),
                "planned_amount": st.column_config.NumberColumn("计划投入", min_value=0.0, format="%.2f"),
            },
            disabled=["planned_amount"],
        )
        if st.button("创建", type="primary"):
            meta = st.session_state.get("dialog_generated_meta", {})
            if not meta.get("symbol"):
                st.error("标的代码不能为空。")
                return
            try:
                adjusted = []
                seen_indexes = set()
                for row in edited.to_dict(orient="records"):
                    level_index = int(row["level_index"])
                    target_price = float(row["target_price"])
                    planned_shares = int(row["planned_shares"])
                    planned_amount = round(target_price * planned_shares, 2)
                    if level_index < 1:
                        raise ValueError("LV 编号必须大于 0。")
                    if level_index in seen_indexes:
                        raise ValueError("LV 编号不能重复。")
                    if target_price <= 0:
                        raise ValueError("触发价格必须大于 0。")
                    if planned_shares <= 0:
                        raise ValueError("计划股数必须大于 0。")
                    if planned_amount <= 0:
                        raise ValueError("计划投入必须大于 0。")
                    seen_indexes.add(level_index)
                    adjusted.append(
                        GeneratedLevel(
                            level_index=level_index,
                            target_price=target_price,
                            planned_shares=planned_shares,
                            planned_amount=planned_amount,
                        )
                    )
                instrument_id = create_plan_with_levels_local(
                    symbol=meta["symbol"],
                    name=meta.get("name", ""),
                    category=meta.get("category", ""),
                    levels=adjusted,
                    trigger_pct=(
                        float(meta["trigger_pct"]) if meta.get("trigger_pct") is not None else None
                    ),
                )
                st.session_state["selected_instrument_id"] = instrument_id
                st.session_state.pop("dialog_generated_levels", None)
                st.session_state.pop("dialog_generated_meta", None)
                rerun()
            except sqlite3.IntegrityError:
                st.error("创建失败：标的代码已存在，或 LV 编号重复。")
            except ValueError as exc:
                st.error(str(exc))


def render_new_plan_button() -> None:
    left, _ = st.columns([0.35, 6])
    if left.button("＋", width="stretch", help="新建分档计划"):
        quick_create_dialog()


def handle_overview_action() -> None:
    action = query_param("overview_action")
    instrument_id_value = query_param("instrument_id")
    if not action:
        return

    if action == "refresh_all":
        quotes, errors = refresh_all_prices_local()
        if quotes:
            st.session_state["overview_flash"] = (
                f"已更新 {len(quotes)} 个标的："
                + "，".join(f"{quote.symbol} {price(quote.price)}" for quote in quotes)
            )
        if errors:
            st.session_state["overview_flash_error"] = (
                f"{len(errors)} 个标的更新失败：" + "；".join(errors)
            )
        if not quotes and not errors:
            st.session_state["overview_flash_error"] = "没有可更新的 active 标的。"
        clear_query_params()
        rerun()
        return

    if not instrument_id_value:
        clear_query_params()
        rerun()
        return

    try:
        instrument_id = int(instrument_id_value)
    except ValueError:
        clear_query_params()
        rerun()
        return

    if action == "open":
        st.session_state["selected_instrument_id"] = instrument_id
        st.session_state["page"] = "标的详情"
        clear_query_params()
        rerun()
    elif action == "refresh":
        try:
            quote = refresh_instrument_price_local(instrument_id)
            st.session_state["overview_flash"] = (
                f"{quote.symbol} 已更新：{price(quote.price)}（{quote.quote_date}，{quote.provider}）"
            )
        except Exception as exc:
            st.session_state["overview_flash_error"] = f"价格更新失败：{exc}"
        clear_query_params()
        rerun()
    elif action == "edit":
        edit_instrument_dialog(instrument_id)
    elif action == "delete":
        delete_instrument_dialog(instrument_id)


def handle_level_action() -> None:
    action = query_param("level_action")
    instrument_id_value = query_param("instrument_id")
    level_id_value = query_param("level_id")
    if not action or not instrument_id_value or not level_id_value:
        return

    try:
        instrument_id = int(instrument_id_value)
        level_id = int(level_id_value)
    except ValueError:
        clear_query_params()
        rerun()
        return

    if action == "execute":
        db.mark_level_executed(level_id)
    elif action == "undo":
        db.undo_level_executed(level_id)
    st.session_state["selected_instrument_id"] = instrument_id
    clear_query_params()
    rerun()


def overview_page() -> None:
    handle_overview_action()
    totals = calculate_overview_totals(active_only=True)
    total_columns = st.columns([1, 1, 1.1])
    render_colored_metric(
        total_columns[0],
        "总投资标的数量",
        str(totals["instrument_count"]),
        "inherit",
    )
    render_colored_metric(
        total_columns[1],
        "已投入总投资额",
        money(totals["invested_amount"]),
        "inherit",
    )
    total_return_text = "-"
    if totals["profit_value"] is not None:
        total_return_text = f"{money_signed(totals['profit_value'])}/{percent_signed(totals['profit_pct'])}"
    render_colored_metric(
        total_columns[2],
        "总收益",
        total_return_text,
        signed_color(totals["profit_value"]),
    )
    flash = st.session_state.pop("overview_flash", None)
    flash_error = st.session_state.pop("overview_flash_error", None)
    if flash:
        st.success(flash)
    if flash_error:
        st.error(flash_error)
    frame = services.overview_rows(active_only=True)
    if frame.empty:
        st.info("暂无启用标的。")
        render_new_plan_button()
        return

    for column, default in {
        "建仓价": None,
        "初始投资": None,
        "建仓时间": "",
        "加仓间隔": None,
        "已投": 0.0,
        "收益值": None,
        "收益率": None,
        "needs_action": False,
    }.items():
        if column not in frame.columns:
            frame[column] = default

    if "id" in frame.columns:
        for index, row in frame.iterrows():
            levels = db.list_levels(int(row["id"]))
            first_level = next((level for level in levels if int(level["level_index"]) == 1), None)
            if first_level:
                frame.at[index, "建仓价"] = first_level["target_price"]
                frame.at[index, "初始投资"] = first_level["planned_amount"]
                frame.at[index, "建仓时间"] = first_level["executed_at"] or ""
            frame.at[index, "已投"] = sum(
                float(level["planned_amount"]) for level in levels if int(level["executed"]) == 1
            )
            current_price = row["current_price"]
            if current_price is not None and pd.isna(current_price):
                current_price = None
            stats = executed_position_stats(levels, current_price)
            frame.at[index, "收益值"] = stats["profit_value"]
            frame.at[index, "收益率"] = stats["return_pct"]

    render_overview_table(frame)

    render_new_plan_button()


def detail_header(instrument_id: int) -> None:
    summary = services.instrument_summary(instrument_id)
    if not summary:
        st.warning("标的不存在。")
        return
    instrument = summary["instrument"]
    stats = executed_position_stats(summary["levels"], instrument["current_price"])
    invested_text = money(stats["invested_amount"])
    if stats["invested_shares"]:
        invested_text = f"{invested_text}/{stats['invested_shares']}股"

    total_return_text = "-"
    if stats["profit_value"] is not None:
        total_return_text = f"{money_signed(stats['profit_value'])}/{percent_signed(stats['return_pct'])}"

    triggered_text = "-"
    if summary["triggered_levels"]:
        triggered_text = f"{'/'.join(summary['triggered_levels'])}/{money(summary['triggered_amount'])}"

    header_color = signed_color(stats["profit_value"])
    cols = st.columns([1, 1.4, 1, 1.35, 1.45, 1.35])
    header_metrics = [
        ("标的", instrument["symbol"]),
        ("当前价格", price(instrument["current_price"])),
        ("均价", price(stats["average_cost"])),
        ("已投入", invested_text),
        ("总收益", total_return_text),
        ("待处理", triggered_text),
    ]
    for column, (label, value) in zip(cols, header_metrics, strict=True):
        render_colored_metric(column, label, value, header_color)
    if instrument["notes"]:
        st.caption(instrument["notes"])


def render_level_status_rows(instrument_id: int) -> None:
    instrument = db.get_instrument(instrument_id)
    frame = services.level_rows(instrument_id)
    if frame.empty:
        st.info("该标的还没有档位。")
        return

    current_price = instrument["current_price"] if instrument else None
    labels = ["LV", "触发价格", "计划投入", "买入时间", "收益", "操作"]
    widths = [12, 20, 22, 18, 18, 10]
    header = "".join(f"<th>{html.escape(label)}</th>" for label in labels)
    colgroup = "".join(f"<col style='width: {width}%'>" for width in widths)
    rows = []
    for _, level in frame.iterrows():
        status = str(level["computed_status"])
        level_id = int(level["id"])
        if bool(level["executed"]):
            action = (
                f"<a class='level-action danger' title='撤销已买入' "
                f"href='{level_action_url('undo', instrument_id, level_id)}' "
                "target='_self' rel='noreferrer'>×</a>"
            )
        else:
            action = (
                f"<a class='level-action' title='标记为已买入' "
                f"href='{level_action_url('execute', instrument_id, level_id)}' "
                "target='_self' rel='noreferrer'>✓</a>"
            )
        cells = [
            level["LV"],
            price(level["target_price"]),
            amount_with_shares(level["planned_amount"], level["target_price"]),
            level["executed_at"] or "-",
            level_return_text(
                level["planned_amount"],
                level["target_price"],
                current_price,
                bool(level["executed"]),
            ),
            action,
        ]
        cell_html = "".join(
            f"<td>{cell}</td>"
            if isinstance(cell, str) and cell.startswith("<a ")
            else f"<td>{html.escape(str(cell))}</td>"
            for cell in cells
        )
        rows.append(f"<tr class='{html.escape(status)}'>{cell_html}</tr>")

    st.markdown(
        f"""
        <style>
        .level-table {{
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
            margin-top: 0.5rem;
            margin-bottom: 0.75rem;
            color: #f9fafb;
        }}
        .level-table th,
        .level-table td {{
            border: 1px solid rgba(250, 250, 250, 0.18);
            padding: 0.45rem 0.55rem;
            line-height: 1.25;
            vertical-align: middle;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .level-table th {{
            background: rgba(250, 250, 250, 0.06);
            font-weight: 700;
        }}
        .level-table tr.executed td {{
            color: #f9fafb;
            font-weight: 500;
        }}
        .level-table tr.triggered td {{
            background: #ffe4e6;
            color: #7f1d1d;
            font-weight: 700;
        }}
        .level-table tr.pending td {{
            background: #dcfce7;
            color: #14532d;
            font-weight: 600;
        }}
        .level-table tr.unknown td {{
            background: #f8fafc;
            color: #334155;
            font-weight: 500;
        }}
        .level-action {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.45rem;
            height: 1.45rem;
            border: 1px solid rgba(250, 250, 250, 0.28);
            border-radius: 0.2rem;
            color: inherit;
            font-weight: 800;
            text-decoration: none;
        }}
        .level-action:hover {{
            background: rgba(250, 250, 250, 0.12);
        }}
        .level-action.danger {{
            color: #fca5a5;
        }}
        </style>
        <table class="level-table">
            <colgroup>{colgroup}</colgroup>
            <thead><tr>{header}</tr></thead>
            <tbody>{"".join(rows)}</tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )


def level_management(instrument_id: int) -> None:
    levels = db.list_levels(instrument_id)
    left, right, _ = st.columns([0.35, 0.35, 6])
    add_disabled = not levels
    delete_disabled = len(levels) <= 1

    if left.button("＋", disabled=add_disabled, width="stretch", help="新增下一档"):
        try:
            services.create_next_level(instrument_id)
            rerun()
        except (ValueError, sqlite3.IntegrityError) as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"新增下一档失败：{exc}")

    if right.button("－", disabled=delete_disabled, width="stretch", help="删除最低档"):
        try:
            deleted_index = services.delete_lowest_level(instrument_id)
            st.success(f"已删除 LV{deleted_index}。")
            rerun()
        except (ValueError, sqlite3.Error) as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"删除最低档失败：{exc}")

    if add_disabled:
        return
    elif delete_disabled:
        return


def detail_page() -> None:
    handle_level_action()
    all_instruments = instrument_options(active_only=True)
    if not all_instruments:
        st.info("还没有标的，请先新增或快速创建分档计划。")
        return

    selected_id = int(st.session_state.get("selected_instrument_id", all_instruments[0]["id"]))
    if db.get_instrument(selected_id) is None:
        selected_id = all_instruments[0]["id"]
        st.session_state["selected_instrument_id"] = selected_id

    selected = db.get_instrument(selected_id)

    option_by_symbol = {row["symbol"]: row for row in all_instruments}
    labels = list(option_by_symbol)
    current_label = selected["symbol"]
    selected_label = st.selectbox(
        "标的",
        labels,
        index=labels.index(current_label),
        key="detail_select",
        label_visibility="collapsed",
    )
    new_id = int(option_by_symbol[selected_label]["id"])
    if new_id != selected_id:
        st.session_state["selected_instrument_id"] = new_id
        rerun()
    instrument_id = new_id

    detail_header(instrument_id)

    render_level_status_rows(instrument_id)
    level_management(instrument_id)


def backup_page() -> None:
    st.subheader("数据备份")
    col1, col2 = st.columns(2)
    col1.download_button(
        "导出标的 CSV",
        data=services.export_instruments_csv(),
        file_name="instruments.csv",
        mime="text/csv",
        width="stretch",
    )
    col2.download_button(
        "导出档位 CSV",
        data=services.export_levels_csv(),
        file_name="levels.csv",
        mime="text/csv",
        width="stretch",
    )

    st.divider()
    st.write("CSV 导入")
    instruments_file = st.file_uploader("导入标的 CSV", type=["csv"], key="import_instruments")
    if instruments_file and st.button("导入标的"):
        count = services.import_instruments_csv(instruments_file.getvalue().decode("utf-8"))
        st.success(f"已导入或更新 {count} 条标的。")
        rerun()

    levels_file = st.file_uploader("导入档位 CSV", type=["csv"], key="import_levels")
    if levels_file and st.button("导入档位"):
        count = services.import_levels_csv(levels_file.getvalue().decode("utf-8"))
        st.success(f"已导入或更新 {count} 条档位。")
        rerun()


def top_navigation(pages: list[str], default_page: str) -> str:
    columns = st.columns([0.7, 0.9, 0.8, 6])
    for column, page in zip(columns[: len(pages)], pages, strict=True):
        if column.button(
            page,
            key=f"top_nav_{page}",
            type="primary" if page == default_page else "secondary",
            width="stretch",
        ):
            if page != default_page:
                st.session_state["page"] = page
                rerun()
    return default_page


def main() -> None:
    db.init_db()
    apply_global_styles()

    pages = ["总览", "标的详情", "数据备份"]
    if query_param("level_action"):
        st.session_state["page"] = "标的详情"
    default_page = st.session_state.get("page", "总览")
    if default_page not in pages:
        default_page = "总览"
    page = top_navigation(pages, default_page)
    st.session_state["page"] = page

    if page == "总览":
        overview_page()
    elif page == "标的详情":
        detail_page()
    elif page == "数据备份":
        backup_page()


if __name__ == "__main__":
    main()
