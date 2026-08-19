from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation


TONGHUASHUN_EXTERNAL_SOURCE = "tonghuashun_delivery"
REQUIRED_COLUMNS = {
    "成交日期",
    "成交时间",
    "证券代码",
    "证券名称",
    "操作",
    "成交数量",
    "成交编号",
    "成交均价",
}
FEE_COLUMNS = ("手续费", "印花税", "过户费", "其他费用")


@dataclass(frozen=True)
class TonghuashunDeliveryRecord:
    trade_at: str
    symbol: str
    name: str
    side: str
    shares: float
    price: float
    fees: float
    amount: float
    market_name: str
    external_order_id: str

    def preview_row(self) -> dict[str, object]:
        return {
            "成交时间": self.trade_at,
            "标的/名称": f"{self.symbol}/{self.name}",
            "方向": "买入" if self.side == "BUY" else "卖出",
            "成交价": self.price,
            "股数": self.shares,
            "费用": self.fees,
            "成交编号": self.external_order_id.rsplit(":", 1)[-1],
        }


def decode_tonghuashun_file(content: bytes) -> str:
    if not content:
        raise ValueError("交割单文件为空。")
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("无法识别交割单编码，请从同花顺重新导出。")


def parse_tonghuashun_delivery(content: bytes) -> list[TonghuashunDeliveryRecord]:
    text = decode_tonghuashun_file(content)
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    fieldnames = {str(name).strip() for name in (reader.fieldnames or []) if name is not None}
    missing_columns = sorted(REQUIRED_COLUMNS - fieldnames)
    if missing_columns:
        raise ValueError(f"交割单缺少字段：{' / '.join(missing_columns)}。")

    records: list[TonghuashunDeliveryRecord] = []
    seen_external_ids: set[str] = set()
    for row_number, raw_row in enumerate(reader, start=2):
        row = {
            str(key).strip(): str(value or "").strip()
            for key, value in raw_row.items()
            if key is not None
        }
        if not any(row.values()):
            continue

        side = parse_side(row.get("操作", ""), row_number)
        symbol = row.get("证券代码", "").strip().upper()
        name = row.get("证券名称", "").strip()
        order_number = row.get("成交编号", "").strip()
        if not symbol:
            raise ValueError(f"第 {row_number} 行证券代码为空。")
        if not order_number:
            raise ValueError(f"第 {row_number} 行成交编号为空。")

        trade_at = parse_trade_at(
            row.get("成交日期", ""),
            row.get("成交时间", ""),
            row_number,
        )
        shares = abs(parse_nonzero_number(row.get("成交数量", ""), "成交数量", row_number))
        price = parse_positive_number(row.get("成交均价", ""), "成交均价", row_number)
        amount = parse_optional_number(row.get("成交金额", ""), "成交金额", row_number)
        fees = sum(
            abs(parse_optional_number(row.get(column, ""), column, row_number))
            for column in FEE_COLUMNS
        )
        market_name = row.get("交易市场", "") or row.get("市场名称", "")
        external_order_id = f"{row.get('成交日期', '')}:{symbol}:{order_number}"
        if external_order_id in seen_external_ids:
            continue
        seen_external_ids.add(external_order_id)
        records.append(
            TonghuashunDeliveryRecord(
                trade_at=trade_at,
                symbol=symbol,
                name=name,
                side=side,
                shares=shares,
                price=price,
                fees=round(fees, 4),
                amount=amount,
                market_name=market_name.strip(),
                external_order_id=external_order_id,
            )
        )

    if not records:
        raise ValueError("交割单中没有可导入的成交记录。")
    return sorted(records, key=lambda item: (item.trade_at, item.external_order_id))


def parse_side(value: str, row_number: int) -> str:
    cleaned = value.strip()
    if "买入" in cleaned:
        return "BUY"
    if "卖出" in cleaned:
        return "SELL"
    raise ValueError(f"第 {row_number} 行操作类型不支持：{cleaned or '空'}。")


def parse_trade_at(date_value: str, time_value: str, row_number: int) -> str:
    combined = f"{date_value.strip()} {time_value.strip()}".strip()
    for date_format in ("%Y%m%d %H:%M:%S", "%Y%m%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            parsed = datetime.strptime(combined, date_format)
            return parsed.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            continue
    raise ValueError(f"第 {row_number} 行成交时间无法识别：{combined or '空'}。")


def parse_positive_number(value: str, field: str, row_number: int) -> float:
    number = parse_optional_number(value, field, row_number)
    if number <= 0:
        raise ValueError(f"第 {row_number} 行{field}必须大于 0。")
    return number


def parse_nonzero_number(value: str, field: str, row_number: int) -> float:
    number = parse_optional_number(value, field, row_number)
    if number == 0:
        raise ValueError(f"第 {row_number} 行{field}不能为 0。")
    return number


def parse_optional_number(value: str, field: str, row_number: int) -> float:
    cleaned = value.strip().replace(",", "")
    if not cleaned:
        return 0.0
    try:
        return float(Decimal(cleaned))
    except (InvalidOperation, ValueError):
        raise ValueError(f"第 {row_number} 行{field}无法识别：{value}。") from None
