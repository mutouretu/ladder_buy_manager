from __future__ import annotations

import html
import importlib
import sqlite3
from datetime import datetime
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

import db
import market_data
import services
import trade_db
import trade_services
from models import GeneratedLevel


trade_db = importlib.reload(trade_db)
trade_services = importlib.reload(trade_services)


st.set_page_config(page_title="分档买入管理器", layout="wide", initial_sidebar_state="expanded")


def now_minute_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def apply_global_styles() -> None:
    st.markdown(
        """
        <style>
        header[data-testid="stHeader"] {
            background: transparent !important;
            box-shadow: none !important;
        }
        div[data-testid="stDecoration"] {
            display: none !important;
        }
        .block-container {
            max-width: 100% !important;
            padding-left: 1.25rem !important;
            padding-right: 1.25rem !important;
            padding-top: 2.2rem !important;
        }
        section[data-testid="stSidebar"][aria-expanded="true"] {
            width: 13rem !important;
            min-width: 13rem !important;
        }
        section[data-testid="stSidebar"][aria-expanded="true"] > div {
            width: 13rem !important;
            min-width: 13rem !important;
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


def recommendation_source_action_url(
    action: str,
    source_id: int,
    return_page: str | None = None,
) -> str:
    params = {
        "recommendation_source_action": action,
        "source_id": int(source_id),
    }
    if return_page:
        params["return_page"] = return_page
    return "?" + urlencode(params)


def recommendation_plan_action_url(
    action: str,
    recommendation_id: int,
    return_page: str | None = None,
) -> str:
    params = {
        "recommendation_action": action,
        "recommendation_id": int(recommendation_id),
    }
    if return_page:
        params["return_page"] = return_page
    return "?" + urlencode(params)


def recommendation_source_refresh_url(source_id: int, return_page: str = "项目详情") -> str:
    return recommendation_source_action_url("refresh_prices", source_id, return_page)


def recommendation_global_refresh_url() -> str:
    return recommendation_source_action_url("refresh_all_prices", 0, "总览")


def stock_operation_url(recommendation_id: int) -> str:
    return "?" + urlencode(
        {
            "recommendation_action": "open_stock",
            "recommendation_id": int(recommendation_id),
        }
    )


def trade_order_action_url(action: str, order_id: int) -> str:
    return "?" + urlencode(
        {
            "trade_order_action": action,
            "trade_order_id": int(order_id),
        }
    )


def trade_ladder_action_url(action: str, level_id: int) -> str:
    return "?" + urlencode(
        {
            "trade_ladder_action": action,
            "trade_ladder_level_id": int(level_id),
        }
    )


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
    label_color = color if color != "inherit" else "#6b7280"
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


def colored_money_text(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    css_class = "return-flat"
    if float(value) > 0:
        css_class = "return-positive"
    elif float(value) < 0:
        css_class = "return-negative"
    return f"<span class='{css_class}'>{html.escape(money_signed(value))}</span>"


def overview_total_profit_text(value: float | None, return_pct: float | None) -> str:
    if value is None or pd.isna(value):
        return ""
    numeric = float(value)
    text = money_signed(numeric)
    if return_pct is not None:
        text = f"{text}/{percent_signed(return_pct)}"
    if numeric > 0:
        return f"<span class='return-positive'>{html.escape(text)}</span>"
    if numeric < 0:
        return f"<span class='return-negative'>{html.escape(text)}</span>"
    return ""


def source_total_return_pct(row: pd.Series) -> float | None:
    invested = row.get("投入金额折算")
    total_profit = row.get("总收益折算")
    if invested is None or total_profit is None or pd.isna(invested) or pd.isna(total_profit):
        return None
    if float(invested) <= 0:
        return None
    return float(total_profit) / float(invested) * 100


def colored_percent_text(value: float | None, none_as_zero: bool = False) -> str:
    if value is None or pd.isna(value):
        if not none_as_zero:
            return "-"
        value = 0.0
    css_class = "return-flat"
    if float(value) > 0:
        css_class = "return-positive"
    elif float(value) < 0:
        css_class = "return-negative"
    return f"<span class='{css_class}'>{html.escape(percent_signed(value))}</span>"


def invested_return_text(invested_amount: float | None, return_pct: float | None) -> str:
    invested = 0.0 if invested_amount is None or pd.isna(invested_amount) else float(invested_amount)
    return (
        f"<span class='return-flat'>{html.escape(money(invested))}</span>/"
        f"{colored_percent_text(return_pct, none_as_zero=True)}"
    )


TRADE_IDEA_COLUMNS = [
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


def ensure_trade_idea_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty and not set(TRADE_IDEA_COLUMNS).issubset(frame.columns):
        return pd.DataFrame(columns=TRADE_IDEA_COLUMNS)
    for column in TRADE_IDEA_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA
    return frame


def optional_positive_float(value: float | int | None) -> float | None:
    if value is None or pd.isna(value):
        return None
    numeric = float(value)
    return numeric if numeric > 0 else None


def recommendation_sources_mock() -> list[dict]:
    return [dict(source) for source in trade_services.source_rows()]


def get_recommendation_source(source_id: int) -> dict | None:
    source = trade_services.get_source(source_id)
    return dict(source) if source is not None else None


RECOMMENDATION_MARKETS = ["美股", "A股", "港股", "加密"]


def create_recommendation_source_mock(name: str, market: str) -> None:
    trade_services.create_source(name, market)


def update_recommendation_source_mock(source_id: int, name: str, market: str) -> None:
    trade_services.update_source(source_id, name, market)


def delete_recommendation_source_mock(source_id: int) -> None:
    trade_services.delete_source(source_id)


def recommendations_mock() -> list[dict]:
    return [
        {
            "id": idea["id"],
            "source_id": idea["source_id"],
            "symbol": idea["symbol"],
            "name": idea["name"] or "",
            "recommended_at": idea["idea_at"],
            "recommendation_price": idea["plan_price"],
            "current_price": idea["current_price"],
            "manual_status": idea["status"],
        }
        for idea in trade_db.list_ideas()
    ]


def get_recommendation_plan(recommendation_id: int) -> dict | None:
    idea = trade_services.get_idea(recommendation_id)
    if idea is None:
        return None
    return {
        "id": idea["id"],
        "source_id": idea["source_id"],
        "symbol": idea["symbol"],
        "name": idea["name"] or "",
        "recommended_at": idea["idea_at"],
        "recommendation_price": idea["plan_price"],
        "current_price": idea["current_price"],
        "manual_status": idea["status"],
    }


def create_recommendation_plan_mock(
    source_id: int,
    symbol: str,
    name: str,
    recommended_at: str,
    recommendation_price: float,
    current_price: float,
) -> None:
    trade_services.create_idea(
        source_id=source_id,
        symbol=symbol,
        name=name,
        idea_at=recommended_at,
        plan_price=recommendation_price,
        current_price=current_price,
    )


def update_recommendation_plan_mock(
    recommendation_id: int,
    symbol: str,
    name: str,
    recommended_at: str,
    recommendation_price: float,
    current_price: float,
) -> None:
    trade_services.update_idea(
        idea_id=recommendation_id,
        symbol=symbol,
        name=name,
        idea_at=recommended_at,
        plan_price=recommendation_price,
        current_price=current_price,
    )


def delete_recommendation_plan_mock(recommendation_id: int) -> None:
    trade_services.delete_idea(recommendation_id)


def complete_recommendation_plan_mock(recommendation_id: int) -> None:
    trade_services.complete_idea(recommendation_id)


def recommendation_trades_mock() -> list[dict]:
    return trade_services.order_rows()


def recommendation_rows() -> pd.DataFrame:
    return trade_services.idea_rows()


def recommendation_source_summary() -> pd.DataFrame:
    return trade_services.source_summary()


@st.dialog("新增项目")
def create_recommendation_source_dialog() -> None:
    with st.form("create_recommendation_source_form"):
        name = st.text_input("项目名称")
        market = st.selectbox("市场", RECOMMENDATION_MARKETS)
        submitted = st.form_submit_button("保存", type="primary")
    if submitted:
        try:
            create_recommendation_source_mock(name, market)
            rerun()
        except ValueError as exc:
            st.error(str(exc))


@st.dialog("编辑项目")
def edit_recommendation_source_dialog(source_id: int) -> None:
    source = get_recommendation_source(source_id)
    if source is None:
        st.warning("项目不存在，可能已经被删除。")
        return
    with st.form(f"edit_recommendation_source_form_{source_id}"):
        name = st.text_input("项目名称", value=source["name"])
        market = st.selectbox(
            "市场",
            RECOMMENDATION_MARKETS,
            index=RECOMMENDATION_MARKETS.index(source.get("market", "美股")),
        )
        submitted = st.form_submit_button("保存", type="primary")
    if submitted:
        try:
            update_recommendation_source_mock(source_id, name, market)
            clear_query_params()
            rerun()
        except ValueError as exc:
            st.error(str(exc))


@st.dialog("确认删除")
def delete_recommendation_source_dialog(source_id: int) -> None:
    source = get_recommendation_source(source_id)
    if source is None:
        st.warning("项目不存在，可能已经被删除。")
        return
    st.write(f"确定删除 {source['name']} 吗？")
    st.caption("删除后该项目及其交易计划会从页面隐藏。")
    left, right = st.columns(2)
    if left.button("是", type="primary", width="stretch"):
        delete_recommendation_source_mock(source_id)
        clear_query_params()
        rerun()
    if right.button("否", width="stretch"):
        clear_query_params()
        rerun()


def handle_recommendation_source_action() -> None:
    action = query_param("recommendation_source_action")
    source_id_value = query_param("source_id")
    return_page = query_param("return_page") or "总览"
    if not action or not source_id_value:
        return
    try:
        source_id = int(source_id_value)
    except ValueError:
        clear_query_params()
        rerun()
        return

    clear_query_params()
    if action == "open":
        source = get_recommendation_source(source_id)
        if source is not None:
            st.session_state["selected_trade_source_name"] = source["name"]
        st.session_state["section"] = "交易管理"
        st.session_state["page"] = "项目详情"
        rerun()
    elif action == "edit":
        edit_recommendation_source_dialog(source_id)
    elif action == "delete":
        delete_recommendation_source_dialog(source_id)
    elif action == "refresh_prices":
        source = get_recommendation_source(source_id)
        if source is not None:
            st.session_state["selected_trade_source_name"] = source["name"]
        try:
            success_count, failures = refresh_trade_source_prices(source_id)
            if failures:
                st.warning(f"已更新 {success_count} 个，失败 {len(failures)} 个：{'；'.join(failures[:3])}")
            else:
                st.success(f"已更新 {success_count} 个标的价格。")
            st.session_state["section"] = "交易管理"
            st.session_state["page"] = return_page
        except Exception as exc:
            st.error(f"批量更新失败：{exc}")
    elif action == "refresh_all_prices":
        try:
            success_count, failures = refresh_all_trade_prices()
            if failures:
                st.warning(f"已更新 {success_count} 个，失败 {len(failures)} 个：{'；'.join(failures[:5])}")
            else:
                st.success(f"已更新 {success_count} 个标的价格。")
            st.session_state["section"] = "交易管理"
            st.session_state["page"] = return_page
        except Exception as exc:
            st.error(f"全部更新失败：{exc}")


@st.dialog("新增标的")
def create_recommendation_plan_dialog(source_id: int) -> None:
    source = get_recommendation_source(source_id)
    if source is None:
        st.warning("项目不存在，可能已经被删除。")
        return
    with st.form(f"create_recommendation_plan_form_{source_id}"):
        symbol = st.text_input("标的代码")
        name = st.text_input("名称")
        recommended_at = idea_datetime_input(f"create_recommendation_plan_{source_id}", now_minute_iso())
        recommendation_price = st.number_input("计划价", min_value=0.0, step=0.01, format="%.2f")
        current_price = st.number_input("当前价", min_value=0.0, step=0.01, format="%.2f")
        submitted = st.form_submit_button("保存", type="primary")
    if submitted:
        try:
            create_recommendation_plan_mock(
                source_id,
                symbol,
                name,
                recommended_at,
                optional_positive_float(recommendation_price),
                optional_positive_float(current_price),
            )
            st.session_state["selected_trade_source_name"] = source["name"]
            rerun()
        except ValueError as exc:
            st.error(str(exc))


@st.dialog("编辑标的")
def edit_recommendation_plan_dialog(recommendation_id: int) -> None:
    recommendation = get_recommendation_plan(recommendation_id)
    if recommendation is None:
        st.warning("标的不存在，可能已经被删除。")
        return
    with st.form(f"edit_recommendation_plan_form_{recommendation_id}"):
        symbol = st.text_input("标的代码", value=str(recommendation["symbol"]))
        name = st.text_input("名称", value=str(recommendation["name"]))
        recommended_at = idea_datetime_input(
            f"edit_recommendation_plan_{recommendation_id}",
            recommendation["recommended_at"],
        )
        recommendation_price = st.number_input(
            "计划价",
            min_value=0.0,
            value=(
                float(recommendation["recommendation_price"])
                if recommendation["recommendation_price"] is not None
                else 0.0
            ),
            step=0.01,
            format="%.2f",
        )
        current_price = st.number_input(
            "当前价",
            min_value=0.0,
            value=(
                float(recommendation["current_price"])
                if recommendation["current_price"] is not None
                else 0.0
            ),
            step=0.01,
            format="%.2f",
        )
        submitted = st.form_submit_button("保存", type="primary")
        delete_submitted = st.form_submit_button("删除")
    if delete_submitted:
        delete_recommendation_plan_mock(recommendation_id)
        clear_query_params()
        rerun()
    if submitted:
        try:
            update_recommendation_plan_mock(
                recommendation_id,
                symbol,
                name,
                recommended_at,
                optional_positive_float(recommendation_price),
                optional_positive_float(current_price),
            )
            clear_query_params()
            rerun()
        except ValueError as exc:
            st.error(str(exc))


@st.dialog("删除标的")
def delete_recommendation_plan_dialog(recommendation_id: int) -> None:
    recommendation = get_recommendation_plan(recommendation_id)
    if recommendation is None:
        st.warning("标的不存在，可能已经被删除。")
        return
    st.write(f"确定删除 {recommendation['symbol']} 吗？")
    left, right = st.columns(2)
    if left.button("是", type="primary", width="stretch"):
        delete_recommendation_plan_mock(recommendation_id)
        return_page = st.session_state.get("recommendation_action_return_page")
        clear_query_params()
        if return_page:
            st.session_state["section"] = "交易管理"
            st.session_state["page"] = return_page
            st.session_state.pop("recommendation_action_return_page", None)
        rerun()
    if right.button("否", width="stretch"):
        return_page = st.session_state.get("recommendation_action_return_page")
        clear_query_params()
        if return_page:
            st.session_state["section"] = "交易管理"
            st.session_state["page"] = return_page
            st.session_state.pop("recommendation_action_return_page", None)
        rerun()


def handle_recommendation_plan_action() -> None:
    action = query_param("recommendation_action")
    recommendation_id_value = query_param("recommendation_id")
    return_page = query_param("return_page")
    if return_page == "交易历史":
        return_page = "项目详情"
    if return_page == "来源详情":
        return_page = "项目详情"
    if not action or not recommendation_id_value:
        return
    try:
        recommendation_id = int(recommendation_id_value)
    except ValueError:
        clear_query_params()
        rerun()
        return

    recommendation = get_recommendation_plan(recommendation_id)
    if recommendation is not None:
        source = get_recommendation_source(int(recommendation["source_id"]))
        if source is not None:
            st.session_state["selected_trade_source_name"] = source["name"]
    if return_page:
        st.session_state["recommendation_action_return_page"] = return_page

    clear_query_params()
    if action == "refresh":
        try:
            quote = refresh_trade_idea_price(recommendation_id)
            st.toast(f"{quote.symbol} 已更新：{price(quote.price)}")
            rerun()
        except Exception as exc:
            st.error(f"价格更新失败：{exc}")
    elif action == "edit":
        edit_recommendation_plan_dialog(recommendation_id)
    elif action == "delete":
        delete_recommendation_plan_dialog(recommendation_id)
    elif action == "complete":
        try:
            complete_recommendation_plan_mock(recommendation_id)
            rerun()
        except ValueError as exc:
            st.error(str(exc))
    elif action == "restore":
        trade_services.recover_idea_to_watchlist(recommendation_id)
        st.session_state["section"] = "交易管理"
        st.session_state["page"] = "项目详情"
        rerun()
    elif action == "open_stock":
        st.session_state["section"] = "交易管理"
        st.session_state["page"] = "个股操作"
        st.session_state["selected_trade_recommendation_id"] = recommendation_id
        rerun()


def render_recommendation_source_table(summary: pd.DataFrame) -> None:
    labels = [
        "序号",
        "项目/市场",
        "标的",
        "持仓/清仓",
        "浮动(USD)",
        "总收益/收益率",
        "胜率",
        "操作",
    ]
    widths = [5, 28, 8, 12, 13, 14, 12, 8]
    header_cells = []
    for label in labels:
        if label == "操作":
            header_cells.append(
                "<th>"
                "<span class='recommendation-operation-header'>"
                "操作"
                f"<a class='recommendation-action' title='刷新全部观察和持仓价格' "
                f"href='{recommendation_global_refresh_url()}' target='_self' rel='noreferrer'>↻</a>"
                "</span>"
                "</th>"
            )
        else:
            header_cells.append(f"<th>{html.escape(label)}</th>")
    header = "".join(header_cells)
    colgroup = "".join(f"<col style='width: {width}%'>" for width in widths)
    rows = []

    for row_index, row in summary.sort_values("总收益折算", ascending=False).reset_index(drop=True).iterrows():
        source_id = int(row["id"])
        total_return_pct = source_total_return_pct(row)
        cells = [
            row_index + 1,
            (
                f"<a class='recommendation-link' title='打开项目详情' "
                f"href='{recommendation_source_action_url('open', source_id)}' target='_self' rel='noreferrer'>"
                f"{html.escape(str(row['name']))}/{html.escape(str(row['market']))}"
                f"/{html.escape(str(row['币种']))}</a>"
            ),
            int(row["标的数量"]),
            f"{int(row['持仓数量'])}/{int(row['已清仓数量'])}",
            colored_money_text(row["浮动盈亏折算"]),
            overview_total_profit_text(row["总收益折算"], total_return_pct),
            (
                f"{float(row['胜率']):.1f}%"
                if pd.notna(row["胜率"])
                else "-"
            ),
            (
                "<span class='recommendation-actions'>"
                f"<a class='recommendation-action' title='刷新该项目价格' "
                f"href='{recommendation_source_refresh_url(source_id, '总览')}' target='_self' rel='noreferrer'>↻</a>"
                f"<a class='recommendation-action' title='编辑' "
                f"href='{recommendation_source_action_url('edit', source_id)}' target='_self' rel='noreferrer'>✎</a>"
                f"<a class='recommendation-action danger' title='删除' "
                f"href='{recommendation_source_action_url('delete', source_id)}' target='_self' rel='noreferrer'>×</a>"
                "</span>"
            ),
        ]
        cell_html = "".join(
            f"<td>{cell}</td>"
            if isinstance(cell, str) and cell.startswith(("<a ", "<span "))
            else f"<td>{html.escape(str(cell))}</td>"
            for cell in cells
        )
        rows.append(f"<tr>{cell_html}</tr>")

    st.markdown(
        f"""
        <style>
        .recommendation-table {{
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
            margin-top: 0.5rem;
            margin-bottom: 0.75rem;
            color: inherit;
        }}
        .recommendation-table th,
        .recommendation-table td {{
            border: 1px solid rgba(250, 250, 250, 0.18);
            padding: 0.45rem 0.55rem;
            line-height: 1.25;
            vertical-align: middle;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .recommendation-table th {{
            background: rgba(250, 250, 250, 0.06);
            font-weight: 700;
        }}
        .recommendation-actions {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.35rem;
            width: 100%;
        }}
        .recommendation-operation-header {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.35rem;
            width: 100%;
        }}
        .recommendation-action {{
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
        .recommendation-action:hover {{
            background: rgba(250, 250, 250, 0.12);
        }}
        .recommendation-action.danger {{
            color: #f87171;
        }}
        .recommendation-table .return-positive {{
            color: #22c55e;
            font-weight: 700;
        }}
        .recommendation-table .return-negative {{
            color: #f87171;
            font-weight: 700;
        }}
        .recommendation-link {{
            color: inherit;
            font-weight: 700;
            text-decoration: none;
        }}
        .recommendation-link:hover {{
            text-decoration: underline;
        }}
        </style>
        <table class="recommendation-table">
            <colgroup>{colgroup}</colgroup>
            <thead><tr>{header}</tr></thead>
            <tbody>{"".join(rows)}</tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )


def recommendation_price_pair(left: float | None, right: float | None) -> str:
    return f"{price(left)}/{price(right)}"


def recommendation_plan_current_pair(plan_price: float | None, current_price: float | None) -> str:
    text = recommendation_price_pair(plan_price, current_price)
    if (
        plan_price is not None
        and current_price is not None
        and pd.notna(plan_price)
        and pd.notna(current_price)
        and float(current_price) <= float(plan_price)
    ):
        return f"<span class='return-negative'>{html.escape(text)}</span>"
    return text


def parse_idea_datetime(value: object) -> datetime:
    text = "" if value is None or pd.isna(value) else str(value).strip()
    if not text:
        text = now_minute_iso()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return datetime.strptime(now_minute_iso(), "%Y-%m-%d %H:%M")


def idea_datetime_input(key_prefix: str, value: object) -> str:
    current = parse_idea_datetime(value)
    date_col, time_col = st.columns([1, 1])
    selected_date = date_col.date_input(
        "提出日期",
        value=current.date(),
        key=f"{key_prefix}_idea_date",
    )
    selected_time = time_col.time_input(
        "提出时间",
        value=current.time().replace(second=0, microsecond=0),
        key=f"{key_prefix}_idea_time",
        step=1800,
    )
    return f"{selected_date.isoformat()} {selected_time.strftime('%H:%M')}"


def recommendation_time_cell(value: object) -> str:
    text = "" if value is None or pd.isna(value) else str(value).strip()
    if not text:
        text = now_minute_iso()
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        text = f"{text} 00:00"
    return html.escape(text)


def refresh_trade_idea_price(idea_id: int) -> market_data.Quote:
    idea = trade_services.get_idea(idea_id)
    if idea is None:
        raise ValueError("标的不存在。")
    quote = market_data.fetch_latest_price(idea["symbol"])
    trade_db.update_idea_current_price(idea_id, quote.price)
    return quote


def refresh_trade_source_prices(source_id: int) -> tuple[int, list[str]]:
    rows = ensure_trade_idea_columns(recommendation_rows())
    source = get_recommendation_source(source_id)
    if source is None:
        raise ValueError("项目不存在。")
    source_rows = rows[
        (rows["来源"] == source["name"]) & rows["状态"].isin(["观察中", "持仓中"])
    ].copy()
    success_count = 0
    failures: list[str] = []
    for _, row in source_rows.iterrows():
        try:
            refresh_trade_idea_price(int(row["id"]))
            success_count += 1
        except Exception as exc:
            failures.append(f"{row['标的']}: {exc}")
    return success_count, failures


def refresh_all_trade_prices() -> tuple[int, list[str]]:
    rows = ensure_trade_idea_columns(recommendation_rows())
    active_rows = rows[rows["状态"].isin(["观察中", "持仓中"])].copy()
    success_count = 0
    failures: list[str] = []
    for _, row in active_rows.iterrows():
        try:
            refresh_trade_idea_price(int(row["id"]))
            success_count += 1
        except Exception as exc:
            failures.append(f"{row['标的']}: {exc}")
    return success_count, failures


def render_recommendation_detail_table(frame: pd.DataFrame, source_id: int | None = None) -> None:
    labels = ["标的/名称", "提出时间", "计划价/当前价", "买入价/卖出价", "持仓/卖出", "浮盈/实盈", "投入/收益率", "操作"]
    widths = [17, 16, 12, 12, 8, 13, 11, 11]
    header_cells = []
    for label in labels:
        if label == "操作" and source_id is not None:
            header_cells.append(
                "<th>"
                "<span class='recommendation-operation-header'>"
                "操作"
                f"<a class='recommendation-action' title='刷新当前表格价格' "
                f"href='{recommendation_source_refresh_url(source_id)}' target='_self' rel='noreferrer'>↻</a>"
                "</span>"
                "</th>"
            )
        else:
            header_cells.append(f"<th>{html.escape(label)}</th>")
    header = "".join(header_cells)
    colgroup = "".join(f"<col style='width: {width}%'>" for width in widths)
    rows = []

    for _, row in frame.iterrows():
        recommendation_id = int(row["id"])
        action = (
            "<span class='recommendation-actions'>"
            f"<a class='recommendation-action' title='刷新当前价' "
            f"href='{recommendation_plan_action_url('refresh', recommendation_id)}' target='_self' rel='noreferrer'>↻</a>"
            f"<a class='recommendation-action' title='编辑' "
            f"href='{recommendation_plan_action_url('edit', recommendation_id)}' target='_self' rel='noreferrer'>✎</a>"
            f"<a class='recommendation-action complete' title='完成' "
            f"href='{recommendation_plan_action_url('complete', recommendation_id)}' target='_self' rel='noreferrer'>✓</a>"
            "</span>"
        )
        cells = [
            (
                f"<a class='recommendation-link' title='打开个股操作' "
                f"href='{stock_operation_url(recommendation_id)}' target='_self' rel='noreferrer'>"
                f"{html.escape(str(row['标的']))}/{html.escape(str(row['名称']))}</a>"
            ),
            recommendation_time_cell(row["提出时间"]),
            recommendation_plan_current_pair(row["计划价"], row["当前价"]),
            recommendation_price_pair(row["买入价"], row["卖出价"]),
            f"{int(row['持仓股数'])}/{int(row['卖出股数'])}股",
            f"{colored_money_text(row['浮动盈亏'])}/{colored_money_text(row['已实现盈亏'])}",
            invested_return_text(row["投入金额"], row["总收益率"]),
            action,
        ]
        cell_html = "".join(
            f"<td>{cell}</td>"
            if isinstance(cell, str) and cell.startswith(("<a ", "<span "))
            else f"<td>{html.escape(str(cell))}</td>"
            for cell in cells
        )
        rows.append(f"<tr>{cell_html}</tr>")

    st.markdown(
        f"""
        <style>
        .recommendation-table {{
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
            margin-top: 0.5rem;
            margin-bottom: 0.75rem;
            color: inherit;
        }}
        .recommendation-table th,
        .recommendation-table td {{
            border: 1px solid rgba(250, 250, 250, 0.18);
            padding: 0.45rem 0.55rem;
            line-height: 1.25;
            vertical-align: middle;
            overflow-wrap: anywhere;
            white-space: normal;
        }}
        .recommendation-table th {{
            background: rgba(250, 250, 250, 0.06);
            font-weight: 700;
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
        .recommendation-actions {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.28rem;
            width: 100%;
        }}
        .recommendation-operation-header {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.35rem;
            width: 100%;
        }}
        .recommendation-action {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.35rem;
            height: 1.35rem;
            border: 1px solid rgba(250, 250, 250, 0.28);
            border-radius: 0.2rem;
            color: inherit;
            font-weight: 800;
            text-decoration: none;
        }}
        .recommendation-action.complete {{
            color: #22c55e;
        }}
        .recommendation-action.danger {{
            color: #f87171;
        }}
        .recommendation-link {{
            color: inherit;
            font-weight: 700;
            text-decoration: none;
        }}
        .recommendation-link:hover {{
            text-decoration: underline;
        }}
        </style>
        <table class="recommendation-table">
            <colgroup>{colgroup}</colgroup>
            <thead><tr>{header}</tr></thead>
            <tbody>{"".join(rows)}</tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )


def render_trade_history_table(frame: pd.DataFrame, return_page: str = "项目详情") -> None:
    labels = ["标的/名称", "提出时间", "计划价/当前价", "买入价/卖出价", "实盈", "收益率", "状态", "操作"]
    widths = [20, 17, 13, 13, 10, 9, 9, 9]
    header = "".join(f"<th>{html.escape(label)}</th>" for label in labels)
    colgroup = "".join(f"<col style='width: {width}%'>" for width in widths)
    rows = []

    for _, row in frame.iterrows():
        recommendation_id = int(row["id"])
        action = (
            "<span class='recommendation-actions'>"
            f"<a class='recommendation-action' title='回收' "
            f"href='{recommendation_plan_action_url('restore', recommendation_id, return_page)}' "
            "target='_self' rel='noreferrer'>↩</a>"
            f"<a class='recommendation-action danger' title='删除' "
            f"href='{recommendation_plan_action_url('delete', recommendation_id, return_page)}' "
            "target='_self' rel='noreferrer'>×</a>"
            "</span>"
        )
        cells = [
            f"{row['标的']}/{row['名称']}",
            recommendation_time_cell(row["提出时间"]),
            recommendation_price_pair(row["计划价"], row["当前价"]),
            recommendation_price_pair(row["买入价"], row["卖出价"]),
            colored_money_text(row["已实现盈亏"]),
            percent_signed(row["已实现盈亏率"]),
            row["状态"],
            action,
        ]
        cell_html = "".join(
            f"<td>{cell}</td>"
            if isinstance(cell, str) and cell.startswith("<span ")
            else f"<td>{html.escape(str(cell))}</td>"
            for cell in cells
        )
        rows.append(f"<tr>{cell_html}</tr>")

    st.markdown(
        f"""
        <style>
        .recommendation-table {{
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
            margin-top: 0.5rem;
            margin-bottom: 0.75rem;
            color: inherit;
        }}
        .recommendation-table th,
        .recommendation-table td {{
            border: 1px solid rgba(250, 250, 250, 0.18);
            padding: 0.45rem 0.55rem;
            line-height: 1.25;
            vertical-align: middle;
            overflow-wrap: anywhere;
            white-space: normal;
        }}
        .recommendation-table th {{
            background: rgba(250, 250, 250, 0.06);
            font-weight: 700;
        }}
        .recommendation-actions {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.28rem;
            width: 100%;
        }}
        .recommendation-action {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.35rem;
            height: 1.35rem;
            border: 1px solid rgba(250, 250, 250, 0.28);
            border-radius: 0.2rem;
            color: inherit;
            font-weight: 800;
            text-decoration: none;
        }}
        .recommendation-action.danger {{
            color: #f87171;
        }}
        </style>
        <table class="recommendation-table">
            <colgroup>{colgroup}</colgroup>
            <thead><tr>{header}</tr></thead>
            <tbody>{"".join(rows)}</tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )


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
            color: inherit;
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
        st.session_state["section"] = "分档买入管理"
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
            color: inherit;
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


def recommendation_overview_page() -> None:
    handle_recommendation_source_action()
    summary = recommendation_source_summary()
    total_invested = summary["投入金额折算"].sum()
    total_profit = summary["总收益折算"].sum()
    total_recommendations = int(summary["标的数量"].sum())
    best_row = summary.sort_values("总收益折算", ascending=False).iloc[0] if not summary.empty else None

    cols = st.columns([1, 1, 1, 1, 1])
    render_colored_metric(cols[0], "项目数量", str(len(summary)), "inherit")
    render_colored_metric(cols[1], "标的总数", str(total_recommendations), "inherit")
    render_colored_metric(cols[2], "总投入(USD)", money(total_invested), "inherit")
    render_colored_metric(cols[3], "总收益(USD)", money_signed(total_profit), signed_color(total_profit))
    best_text = f"{best_row['name']} {money_signed(best_row['总收益折算'])}" if best_row is not None else "-"
    best_color = signed_color(best_row["总收益折算"]) if best_row is not None else "inherit"
    render_colored_metric(cols[4], "当前最佳", best_text, best_color)

    render_recommendation_source_table(summary)

    left, _ = st.columns([0.35, 6])
    if left.button("＋", width="stretch", help="新增项目"):
        create_recommendation_source_dialog()


def recommendation_detail_page() -> None:
    handle_recommendation_source_action()
    handle_recommendation_plan_action()
    rows = ensure_trade_idea_columns(recommendation_rows())
    summary = recommendation_source_summary()
    if summary.empty:
        st.info("还没有项目，请先在总览里新增项目。")
        return
    source_names = list(summary["name"])
    selected_source_name = st.session_state.get("selected_trade_source_name")
    selected_index = source_names.index(selected_source_name) if selected_source_name in source_names else 0
    selected_source = st.selectbox("项目", source_names, index=selected_index, label_visibility="collapsed")
    st.session_state["selected_trade_source_name"] = selected_source
    source_rows = rows[rows["来源"] == selected_source].copy()
    active_source_rows = source_rows[source_rows["状态"].isin(["观察中", "持仓中"])].copy()
    completed_source_rows = source_rows[source_rows["状态"].isin(["已清仓", "已完成"])].copy()
    source_floating = source_rows["浮动盈亏"].fillna(0).sum()
    source_realized = source_rows["已实现盈亏"].fillna(0).sum()
    source_profit = source_floating + source_realized
    source_invested = source_rows["投入金额"].fillna(0).sum()
    active_observing = int((active_source_rows["状态"] == "观察中").sum())
    active_holding = int((active_source_rows["状态"] == "持仓中").sum())
    completed_count = len(completed_source_rows)

    cols = st.columns([1, 1, 1, 1, 1, 1, 1])
    render_colored_metric(cols[0], "总标的", str(len(source_rows)), "inherit")
    render_colored_metric(cols[1], "计划中", str(active_observing), "inherit")
    render_colored_metric(cols[2], "持仓中", str(active_holding), "inherit")
    render_colored_metric(cols[3], "已完成", str(completed_count), "inherit")
    render_colored_metric(cols[4], "总投入", money(source_invested), "inherit")
    render_colored_metric(cols[5], "浮动盈亏", money_signed(source_floating), signed_color(source_floating))
    render_colored_metric(cols[6], "总盈亏", money_signed(source_profit), signed_color(source_profit))

    source = next(item for item in recommendation_sources_mock() if item["name"] == selected_source)
    st.markdown(
        "\n".join(
            [
                f"**项目**：{source['name']}",
                f"**市场**：{source.get('market', '-')}",
            ]
        )
    )

    st.markdown("**当前计划**")
    if active_source_rows.empty:
        st.info("当前项目没有计划中或正在交易的标的。")
    else:
        render_recommendation_detail_table(active_source_rows, source_id=int(source["id"]))

    left, _ = st.columns([0.35, 6])
    if left.button("＋", width="stretch", help="新增标的"):
        create_recommendation_plan_dialog(int(source["id"]))

    st.markdown("**交易历史**")
    if completed_source_rows.empty:
        st.info("当前项目还没有已完成的交易。")
    else:
        sorted_completed_rows = completed_source_rows.sort_values(
            ["提出时间", "标的"],
            ascending=[False, True],
        )
        render_trade_history_table(sorted_completed_rows, return_page="项目详情")


@st.dialog("买入")
def buy_trade_dialog(idea_id: int, symbol: str) -> None:
    with st.form(f"buy_trade_form_{idea_id}"):
        trade_at = st.text_input("买入时间", value=db.today_iso())
        price_value = st.number_input("买入价格", min_value=0.0, step=0.01, format="%.2f")
        shares = st.number_input("股数", min_value=0, step=1)
        fees = st.number_input("费用", min_value=0.0, step=0.01, format="%.2f")
        submitted = st.form_submit_button("保存", type="primary")
    if submitted:
        try:
            trade_services.create_order(idea_id, "BUY", trade_at, price_value, int(shares), fees)
            st.success(f"{symbol} 买入记录已保存。")
            rerun()
        except ValueError as exc:
            st.error(str(exc))


@st.dialog("卖出")
def sell_trade_dialog(idea_id: int, symbol: str) -> None:
    with st.form(f"sell_trade_form_{idea_id}"):
        trade_at = st.text_input("卖出时间", value=db.today_iso())
        price_value = st.number_input("卖出价格", min_value=0.0, step=0.01, format="%.2f")
        shares = st.number_input("股数", min_value=0, step=1)
        fees = st.number_input("费用", min_value=0.0, step=0.01, format="%.2f")
        submitted = st.form_submit_button("保存", type="primary")
    if submitted:
        try:
            trade_services.create_order(idea_id, "SELL", trade_at, price_value, int(shares), fees)
            st.success(f"{symbol} 卖出记录已保存。")
            rerun()
        except ValueError as exc:
            st.error(str(exc))


@st.dialog("编辑交易记录")
def edit_trade_order_dialog(order_id: int) -> None:
    order = trade_services.get_order(order_id)
    if order is None:
        st.warning("交易记录不存在，可能已经被删除。")
        return
    side_options = {"BUY": "买入", "SELL": "卖出"}
    with st.form(f"edit_trade_order_form_{order_id}"):
        side_label = st.selectbox(
            "方向",
            list(side_options.values()),
            index=list(side_options).index(order["side"]),
        )
        trade_at = st.text_input("交易时间", value=str(order["trade_at"]))
        price_value = st.number_input(
            "价格",
            min_value=0.0,
            value=float(order["price"]),
            step=0.01,
            format="%.2f",
        )
        shares = st.number_input("股数", min_value=0, value=int(order["shares"]), step=1)
        fees = st.number_input(
            "费用",
            min_value=0.0,
            value=float(order["fees"]),
            step=0.01,
            format="%.2f",
        )
        submitted = st.form_submit_button("保存", type="primary")
    if submitted:
        try:
            side = "BUY" if side_label == "买入" else "SELL"
            trade_services.update_order(order_id, side, trade_at, price_value, int(shares), fees)
            st.success("交易记录已保存。")
            rerun()
        except ValueError as exc:
            st.error(str(exc))


@st.dialog("删除交易记录")
def delete_trade_order_dialog(order_id: int) -> None:
    order = trade_services.get_order(order_id)
    if order is None:
        st.warning("交易记录不存在，可能已经被删除。")
        return
    st.write("确定删除这条交易记录吗？")
    left, right = st.columns(2)
    if left.button("是", type="primary", width="stretch"):
        trade_services.delete_order(order_id)
        rerun()
    if right.button("否", width="stretch"):
        rerun()


def handle_trade_order_action() -> None:
    action = query_param("trade_order_action")
    order_id_value = query_param("trade_order_id")
    if not action or not order_id_value:
        return
    try:
        order_id = int(order_id_value)
    except ValueError:
        clear_query_params()
        rerun()
        return

    order = trade_services.get_order(order_id)
    if order is not None:
        st.session_state["selected_trade_recommendation_id"] = int(order["idea_id"])
        idea = trade_services.get_idea(int(order["idea_id"]))
        if idea is not None:
            source = get_recommendation_source(int(idea["source_id"]))
            if source is not None:
                st.session_state["selected_trade_source_name"] = source["name"]

    clear_query_params()
    if action == "edit":
        edit_trade_order_dialog(order_id)
    elif action == "delete":
        delete_trade_order_dialog(order_id)


def render_trade_order_table(trade_rows: list[dict]) -> None:
    labels = ["方向", "交易时间", "价格", "股数", "费用", "操作"]
    widths = [12, 28, 16, 12, 16, 16]
    header = "".join(f"<th>{html.escape(label)}</th>" for label in labels)
    colgroup = "".join(f"<col style='width: {width}%'>" for width in widths)
    rows = []
    for trade in trade_rows:
        order_id = int(trade["id"])
        side_text = "买入" if trade["side"] == "BUY" else "卖出"
        action = (
            "<span class='trade-order-actions'>"
            f"<a class='trade-order-action' title='编辑' "
            f"href='{trade_order_action_url('edit', order_id)}' target='_self' rel='noreferrer'>✎</a>"
            f"<a class='trade-order-action danger' title='删除' "
            f"href='{trade_order_action_url('delete', order_id)}' target='_self' rel='noreferrer'>×</a>"
            "</span>"
        )
        cells = [
            side_text,
            trade["trade_at"],
            price(trade["price"]),
            int(trade["shares"]),
            price(trade["fees"]),
            action,
        ]
        cell_html = "".join(
            f"<td>{cell}</td>"
            if isinstance(cell, str) and cell.startswith("<span ")
            else f"<td>{html.escape(str(cell))}</td>"
            for cell in cells
        )
        rows.append(f"<tr>{cell_html}</tr>")

    st.markdown(
        f"""
        <style>
        .trade-order-table {{
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
            margin-top: 0.5rem;
            margin-bottom: 0.75rem;
            color: inherit;
        }}
        .trade-order-table th,
        .trade-order-table td {{
            border: 1px solid rgba(250, 250, 250, 0.18);
            padding: 0.45rem 0.55rem;
            line-height: 1.25;
            vertical-align: middle;
            overflow-wrap: anywhere;
            white-space: normal;
        }}
        .trade-order-table th {{
            background: rgba(250, 250, 250, 0.06);
            font-weight: 700;
        }}
        .trade-order-actions {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.28rem;
            width: 100%;
        }}
        .trade-order-action {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.35rem;
            height: 1.35rem;
            border: 1px solid rgba(250, 250, 250, 0.28);
            border-radius: 0.2rem;
            color: inherit;
            font-weight: 800;
            text-decoration: none;
        }}
        .trade-order-action.danger {{
            color: #f87171;
        }}
        </style>
        <table class="trade-order-table">
            <colgroup>{colgroup}</colgroup>
            <thead><tr>{header}</tr></thead>
            <tbody>{"".join(rows)}</tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )


@st.dialog("创建分档计划")
def trade_ladder_plan_dialog(idea_id: int) -> None:
    idea = trade_services.get_idea(idea_id)
    if idea is None:
        st.warning("标的不存在，可能已经被删除。")
        return
    existing = trade_services.get_ladder_plan_for_idea(idea_id)
    anchor_default = (
        float(existing["anchor_price"])
        if existing is not None
        else float(idea["plan_price"] or idea["current_price"] or 0)
    )
    first_shares_default = int(existing["first_shares"]) if existing is not None else None
    trigger_default = float(existing["trigger_pct"]) * 100 if existing is not None else None
    level_count_default = (
        len(trade_services.ladder_status_rows(idea_id)) if existing is not None else 1
    )
    anchor_price = st.number_input(
        "首档价格",
        min_value=0.0,
        value=anchor_default,
        step=0.01,
        format="%.2f",
        key=f"trade_ladder_anchor_{idea_id}",
    )
    first_shares = st.number_input(
        "首档股数",
        min_value=1,
        value=first_shares_default,
        step=1,
        key=f"trade_ladder_first_shares_{idea_id}",
    )
    trigger_pct_percent = st.number_input(
        "触发比例（%）",
        min_value=0.0,
        max_value=99.0,
        value=trigger_default,
        step=0.5,
        format="%.2f",
        key=f"trade_ladder_trigger_{idea_id}",
    )
    level_count = st.number_input(
        "档位数量",
        min_value=1,
        max_value=20,
        value=max(1, int(level_count_default)),
        step=1,
        key=f"trade_ladder_level_count_{idea_id}",
    )

    preview_levels: list[dict] = []
    preview_error = ""
    try:
        if first_shares is None:
            raise ValueError("首档股数不能为空。")
        if trigger_pct_percent is None:
            raise ValueError("触发比例不能为空。")
        preview_levels = trade_services.generate_ladder_levels(
            anchor_price=float(anchor_price),
            first_shares=int(first_shares),
            trigger_pct=float(trigger_pct_percent) / 100,
            level_count=int(level_count),
        )
    except ValueError as exc:
        preview_error = str(exc)

    if preview_error:
        st.warning(preview_error)
    elif preview_levels:
        preview_frame = pd.DataFrame(
            [
                {
                    "LV": f"LV{int(level['level_index'])}",
                    "目标价": float(level["target_price"]),
                    "股数": int(level["planned_shares"]),
                    "金额": float(level["planned_amount"]),
                }
                for level in preview_levels
            ]
        )
        st.dataframe(
            preview_frame,
            width="stretch",
            hide_index=True,
            column_config={
                "目标价": st.column_config.NumberColumn("目标价", format="%.2f"),
                "金额": st.column_config.NumberColumn("金额", format="%.2f"),
            },
        )

    if st.button("保存", type="primary", width="stretch", disabled=bool(preview_error)):
        try:
            trade_services.create_or_replace_ladder_plan(
                idea_id=idea_id,
                anchor_price=float(anchor_price),
                first_shares=int(first_shares),
                trigger_pct=float(trigger_pct_percent) / 100,
                level_count=int(level_count),
            )
            st.success("分档计划已保存。")
            rerun()
        except ValueError as exc:
            st.error(str(exc))


@st.dialog("删除分档计划")
def delete_trade_ladder_plan_dialog(idea_id: int) -> None:
    st.write("确定删除这个分档计划吗？")
    st.caption("已生成的买入记录会保留，但会解除和原 LV 的关联。")
    left, right = st.columns(2)
    if left.button("是", type="primary", width="stretch"):
        trade_services.delete_ladder_plan(idea_id)
        rerun()
    if right.button("否", width="stretch"):
        rerun()


@st.dialog("执行分档买入")
def execute_trade_ladder_level_dialog(level_id: int) -> None:
    level = trade_db.get_ladder_level(level_id)
    if level is None:
        st.warning("分档不存在，可能已经被删除。")
        return
    with st.form(f"execute_trade_ladder_level_form_{level_id}"):
        trade_at = st.text_input("买入时间", value=db.today_iso())
        price_value = st.number_input(
            "买入价格",
            min_value=0.0,
            value=float(level["target_price"]),
            step=0.01,
            format="%.2f",
        )
        shares = st.number_input(
            "股数",
            min_value=1,
            value=int(level["planned_shares"]),
            step=1,
        )
        fees = st.number_input("费用", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        submitted = st.form_submit_button("保存", type="primary")
    if submitted:
        try:
            trade_services.execute_ladder_level(
                level_id=level_id,
                trade_at=trade_at,
                price=price_value,
                shares=int(shares),
                fees=fees,
            )
            st.success("分档买入记录已保存。")
            rerun()
        except ValueError as exc:
            st.error(str(exc))


@st.dialog("执行分档卖出")
def sell_trade_ladder_level_dialog(level_id: int) -> None:
    level = trade_db.get_ladder_level(level_id)
    if level is None:
        st.warning("分档不存在，可能已经被删除。")
        return
    plan = trade_db.get_ladder_plan(int(level["plan_id"]))
    if plan is None:
        st.warning("分档计划不存在，可能已经被删除。")
        return
    idea = trade_services.get_idea(int(plan["idea_id"]))
    ladder_row = next(
        (
            row
            for row in trade_services.ladder_status_rows(int(plan["idea_id"]))
            if int(row["id"]) == int(level_id)
        ),
        None,
    )
    open_shares = int(ladder_row["open_shares"]) if ladder_row else 0
    if open_shares <= 0:
        st.warning("该档位没有可卖出的持仓。")
        return

    default_price = float(idea["current_price"] or level["target_price"]) if idea else float(level["target_price"])
    with st.form(f"sell_trade_ladder_level_form_{level_id}"):
        trade_at = st.text_input("卖出时间", value=db.today_iso())
        price_value = st.number_input(
            "卖出价格",
            min_value=0.0,
            value=default_price,
            step=0.01,
            format="%.2f",
        )
        shares = st.number_input(
            "股数",
            min_value=1,
            max_value=open_shares,
            value=open_shares,
            step=1,
        )
        fees = st.number_input("费用", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        submitted = st.form_submit_button("保存", type="primary")
    if submitted:
        try:
            trade_services.sell_ladder_level(
                level_id=level_id,
                trade_at=trade_at,
                price=price_value,
                shares=int(shares),
                fees=fees,
            )
            st.success("分档卖出记录已保存。")
            rerun()
        except ValueError as exc:
            st.error(str(exc))


def handle_trade_ladder_action() -> None:
    action = query_param("trade_ladder_action")
    level_id_value = query_param("trade_ladder_level_id")
    if not action or not level_id_value:
        return
    try:
        level_id = int(level_id_value)
    except ValueError:
        clear_query_params()
        rerun()
        return

    level = trade_db.get_ladder_level(level_id)
    if level is not None:
        plan = trade_db.get_ladder_plan(int(level["plan_id"]))
        if plan is not None:
            st.session_state["selected_trade_recommendation_id"] = int(plan["idea_id"])
            idea = trade_services.get_idea(int(plan["idea_id"]))
            if idea is not None:
                source = get_recommendation_source(int(idea["source_id"]))
                if source is not None:
                    st.session_state["selected_trade_source_name"] = source["name"]

    clear_query_params()
    if action == "execute":
        execute_trade_ladder_level_dialog(level_id)
    elif action == "sell":
        sell_trade_ladder_level_dialog(level_id)


def render_trade_ladder_table(idea_id: int) -> None:
    rows = trade_services.ladder_status_rows(idea_id)
    if not rows:
        return
    labels = ["LV", "目标价", "计划", "状态", "操作"]
    widths = [10, 22, 28, 18, 22]
    header = "".join(f"<th>{html.escape(label)}</th>" for label in labels)
    colgroup = "".join(f"<col style='width: {width}%'>" for width in widths)
    body = []
    for row in rows:
        action = "-"
        if row["status"] == "executed":
            action = (
                f"<a class='trade-ladder-action danger' title='卖出' "
                f"href='{trade_ladder_action_url('sell', int(row['id']))}' "
                "target='_self' rel='noreferrer'>－</a>"
            )
        elif row["status"] != "sold":
            action = (
                f"<a class='trade-ladder-action' title='买入' "
                f"href='{trade_ladder_action_url('execute', int(row['id']))}' "
                "target='_self' rel='noreferrer'>＋</a>"
            )
        cells = [
            f"LV{int(row['level_index'])}",
            price(row["target_price"]),
            f"{int(row['planned_shares'])}股/{price(row['planned_amount'])}",
            row["状态"],
            action,
        ]
        cell_html = "".join(
            f"<td>{cell}</td>"
            if isinstance(cell, str) and cell.startswith("<a ")
            else f"<td>{html.escape(str(cell))}</td>"
            for cell in cells
        )
        body.append(f"<tr class='{html.escape(str(row['status']))}'>{cell_html}</tr>")

    st.markdown(
        f"""
        <style>
        .trade-ladder-table {{
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
            margin-top: 0.5rem;
            margin-bottom: 0.75rem;
            color: inherit;
        }}
        .trade-ladder-table th,
        .trade-ladder-table td {{
            border: 1px solid rgba(250, 250, 250, 0.18);
            padding: 0.45rem 0.55rem;
            line-height: 1.25;
            vertical-align: middle;
            overflow-wrap: anywhere;
            white-space: normal;
        }}
        .trade-ladder-table th {{
            background: rgba(250, 250, 250, 0.06);
            font-weight: 700;
        }}
        .trade-ladder-table tr.executed td {{
            color: #9ca3af;
        }}
        .trade-ladder-table tr.sold td {{
            color: #9ca3af;
            text-decoration: line-through;
        }}
        .trade-ladder-table tr.triggered td {{
            background: #ffe4e6;
            color: #7f1d1d;
            font-weight: 700;
        }}
        .trade-ladder-table tr.pending td {{
            background: #dcfce7;
            color: #14532d;
            font-weight: 600;
        }}
        .trade-ladder-table tr.unknown td {{
            background: #f8fafc;
            color: #334155;
        }}
        .trade-ladder-action {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.35rem;
            height: 1.35rem;
            border: 1px solid rgba(250, 250, 250, 0.28);
            border-radius: 0.2rem;
            color: inherit;
            font-weight: 800;
            text-decoration: none;
        }}
        .trade-ladder-action.danger {{
            color: #f87171;
        }}
        </style>
        <table class="trade-ladder-table">
            <colgroup>{colgroup}</colgroup>
            <thead><tr>{header}</tr></thead>
            <tbody>{"".join(body)}</tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )


@st.dialog("编辑标的")
def edit_trade_plan_dialog(row: pd.Series) -> None:
    with st.form(f"edit_trade_plan_form_{int(row['id'])}"):
        symbol = st.text_input("标的代码", value=str(row["标的"]))
        name = st.text_input("名称", value=str(row["名称"]))
        plan_at = idea_datetime_input(
            f"edit_trade_plan_{int(row['id'])}",
            row["提出时间"],
        )
        plan_price = st.number_input(
            "计划价",
            min_value=0.0,
            value=float(row["计划价"]) if pd.notna(row["计划价"]) else 0.0,
            step=0.01,
            format="%.2f",
        )
        current_price = st.number_input(
            "当前价",
            min_value=0.0,
            value=float(row["当前价"]) if pd.notna(row["当前价"]) else 0.0,
            step=0.01,
            format="%.2f",
        )
        submitted = st.form_submit_button("保存", type="primary")
    if submitted:
        try:
            trade_services.update_idea(
                idea_id=int(row["id"]),
                symbol=symbol,
                name=name,
                idea_at=plan_at,
                plan_price=optional_positive_float(plan_price),
                current_price=optional_positive_float(current_price),
            )
            st.success(f"{symbol.upper()} 已保存。")
            rerun()
        except ValueError as exc:
            st.error(str(exc))


def stock_operation_page() -> None:
    handle_trade_order_action()
    handle_trade_ladder_action()
    rows = ensure_trade_idea_columns(recommendation_rows())
    summary = recommendation_source_summary()
    if rows.empty or summary.empty:
        st.info("还没有交易计划，请先在总览里新增项目。")
        return

    selected_recommendation_id = st.session_state.get("selected_trade_recommendation_id")
    selected_recommendation = get_recommendation_plan(int(selected_recommendation_id)) if selected_recommendation_id else None
    if selected_recommendation is not None:
        selected_source_object = get_recommendation_source(int(selected_recommendation["source_id"]))
        if selected_source_object is not None:
            st.session_state["selected_trade_source_name"] = selected_source_object["name"]

    source_names = list(summary["name"])
    selected_source_name = st.session_state.get("selected_trade_source_name")
    selected_source_index = source_names.index(selected_source_name) if selected_source_name in source_names else 0
    selected_source = st.selectbox(
        "项目",
        source_names,
        index=selected_source_index,
        label_visibility="collapsed",
    )
    st.session_state["selected_trade_source_name"] = selected_source
    source_rows = rows[rows["来源"] == selected_source].copy()
    if source_rows.empty:
        st.info("当前项目还没有标的。")
        return

    symbol_options = [f"{row['标的']}/{row['名称']}" for _, row in source_rows.iterrows()]
    selected_symbol_index = 0
    if selected_recommendation is not None:
        selected_symbol_value = f"{selected_recommendation['symbol']}/{selected_recommendation['name']}"
        if selected_symbol_value in symbol_options:
            selected_symbol_index = symbol_options.index(selected_symbol_value)
    selected_symbol = st.selectbox(
        "标的",
        symbol_options,
        index=selected_symbol_index,
        label_visibility="collapsed",
    )
    selected_symbol_code = selected_symbol.split("/", 1)[0]
    row = source_rows[source_rows["标的"] == selected_symbol_code].iloc[0]
    st.session_state["selected_trade_recommendation_id"] = int(row["id"])

    trade_rows = [
        trade
        for trade in recommendation_trades_mock()
        if int(trade["recommendation_id"]) == int(row["id"])
    ]
    if trade_rows:
        metric_cols = st.columns([1, 1, 1, 1, 1, 1])
        render_colored_metric(metric_cols[0], "当前价", price(row["当前价"]), "inherit")
        render_colored_metric(metric_cols[1], "计划价", price(row["计划价"]), "inherit")
        render_colored_metric(
            metric_cols[2],
            "买入/卖出均价",
            recommendation_price_pair(row["买入价"], row["卖出价"]),
            "inherit",
        )
        render_colored_metric(metric_cols[3], "持仓/卖出", f"{int(row['持仓股数'])}/{int(row['卖出股数'])}股", "inherit")
        render_colored_metric(metric_cols[4], "投入", money(row["投入金额"]), "inherit")
        render_colored_metric(
            metric_cols[5],
            "收益",
            f"{money_signed(row['总收益'])}/{percent_signed(row['总收益率'])}"
            if pd.notna(row["总收益"])
            else "-",
            signed_color(row["总收益"]),
        )
    else:
        metric_cols = st.columns([1, 1, 1, 1, 1, 1])
        render_colored_metric(metric_cols[0], "当前价", price(row["当前价"]), "inherit")
        render_colored_metric(metric_cols[1], "计划价", price(row["计划价"]), "inherit")
        render_colored_metric(metric_cols[2], "买入/卖出均价", "-/-", "inherit")
        render_colored_metric(metric_cols[3], "持仓/卖出", "0/0股", "inherit")
        render_colored_metric(metric_cols[4], "投入", money(row["投入金额"]), "inherit")
        render_colored_metric(metric_cols[5], "收益", "0.00/+0.00%", "inherit")

    ladder_plan = trade_services.get_ladder_plan_for_idea(int(row["id"]))
    action_cols = st.columns([0.45, 0.55, 0.55, 5])
    if action_cols[0].button("↻", help="刷新价格", width="stretch"):
        try:
            quote = market_data.fetch_latest_price(str(row["标的"]))
            trade_db.update_idea_current_price(int(row["id"]), quote.price)
            st.toast(f"{quote.symbol} 已更新：{price(quote.price)}")
            rerun()
        except Exception as exc:
            st.error(f"价格更新失败：{exc}")
    if action_cols[1].button(
        "✚",
        help="创建或重建分档计划",
        width="stretch",
    ):
        trade_ladder_plan_dialog(int(row["id"]))
    if action_cols[2].button(
        "×",
        disabled=ladder_plan is None,
        help="删除分档计划",
        width="stretch",
    ):
        delete_trade_ladder_plan_dialog(int(row["id"]))

    if ladder_plan is not None:
        st.caption(
            (
                f"首档 {price(ladder_plan['anchor_price'])} / "
                f"{int(ladder_plan['first_shares'])}股 / "
                f"间隔 {float(ladder_plan['trigger_pct']) * 100:.2f}%"
            )
        )
        render_trade_ladder_table(int(row["id"]))

    if trade_rows:
        st.markdown("**交易记录**")
        render_trade_order_table(trade_rows)
    else:
        st.info("这个标的还没有买卖记录。")


def sidebar_navigation(sections: dict[str, list[str]], default_section: str, default_page: str) -> tuple[str, str]:
    selected_section = default_section
    selected_page = default_page
    for section, pages in sections.items():
        with st.sidebar.expander(section, expanded=(section == default_section)):
            for page in pages:
                if st.button(
                    page,
                    key=f"sidebar_nav_{section}_{page}",
                    type="primary"
                    if section == default_section and page == default_page
                    else "secondary",
                    width="stretch",
                ):
                    selected_section = section
                    selected_page = page
                    st.session_state["section"] = section
                    st.session_state["page"] = page
                    if section != default_section or page != default_page:
                        rerun()
    return selected_section, selected_page


def render_page_heading(section: str, page: str) -> None:
    st.markdown(
        (
            "<div style='margin-bottom: 0.65rem;'>"
            f"<div style='font-size: 0.78rem; color: #6b7280; line-height: 1.25;'>"
            f"{html.escape(section)}</div>"
            f"<div style='font-size: 1.55rem; font-weight: 700; line-height: 1.25;'>"
            f"{html.escape(page)}</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def main() -> None:
    db.init_db()
    trade_db.init_trade_schema()
    trade_services.seed_demo_data_if_empty()
    trade_services.sync_all_ladder_plan_prices()
    apply_global_styles()

    sections = {
        "交易管理": ["总览", "项目详情", "个股操作"],
        "分档买入管理": ["总览", "标的详情", "数据备份"],
    }
    legacy_page_map = {
        "荐股总览": "总览",
        "荐股详情": "项目详情",
        "来源详情": "项目详情",
    }
    if st.session_state.get("section") == "荐股管理":
        st.session_state["section"] = "交易管理"
    if st.session_state.get("page") in legacy_page_map:
        st.session_state["page"] = legacy_page_map[st.session_state["page"]]
    if query_param("level_action"):
        st.session_state["section"] = "分档买入管理"
        st.session_state["page"] = "标的详情"
    if query_param("recommendation_source_action"):
        st.session_state["section"] = "交易管理"
        source_return_page = query_param("return_page")
        if source_return_page == "来源详情":
            source_return_page = "项目详情"
        if source_return_page:
            st.session_state["page"] = source_return_page
        elif query_param("recommendation_source_action") == "open":
            st.session_state["page"] = "项目详情"
        else:
            st.session_state["page"] = "总览"
    if query_param("recommendation_action"):
        st.session_state["section"] = "交易管理"
        action_return_page = query_param("return_page") or "项目详情"
        if action_return_page == "来源详情":
            action_return_page = "项目详情"
        st.session_state["page"] = action_return_page
    if query_param("trade_order_action"):
        st.session_state["section"] = "交易管理"
        st.session_state["page"] = "个股操作"
    if query_param("trade_ladder_action"):
        st.session_state["section"] = "交易管理"
        st.session_state["page"] = "个股操作"

    default_section = st.session_state.get("section", "交易管理")
    if default_section not in sections:
        default_section = "交易管理"
    default_page = st.session_state.get("page", sections[default_section][0])
    if default_page not in sections[default_section]:
        default_page = sections[default_section][0]
    section, page = sidebar_navigation(sections, default_section, default_page)
    st.session_state["section"] = section
    st.session_state["page"] = page
    render_page_heading(section, page)

    if section == "分档买入管理" and page == "总览":
        overview_page()
    elif section == "分档买入管理" and page == "标的详情":
        detail_page()
    elif section == "分档买入管理" and page == "数据备份":
        backup_page()
    elif section == "交易管理" and page == "总览":
        recommendation_overview_page()
    elif section == "交易管理" and page == "项目详情":
        recommendation_detail_page()
    elif section == "交易管理" and page == "个股操作":
        stock_operation_page()


if __name__ == "__main__":
    main()
