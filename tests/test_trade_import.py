from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import db
import trade_db
import trade_services


HEADERS = [
    "成交日期",
    "成交时间",
    "证券代码",
    "证券名称",
    "操作",
    "成交数量",
    "成交编号",
    "成交均价",
    "成交金额",
    "手续费",
    "印花税",
    "过户费",
    "其他费用",
    "交易市场",
]
ROWS = [
    ["20260818", "09:30:00", "600545", "卓郎智能", "证券买入", "100", "A1", "4.50", "450", "5", "0", "0.10", "0", "上海Ａ股"],
    ["20260818", "10:30:00", "600545", "卓郎智能", "证券买入", "100", "A2", "4.70", "470", "5", "0", "0.10", "0", "上海Ａ股"],
    ["20260819", "11:00:00", "600545", "卓郎智能", "证券卖出", "-200", "A3", "4.80", "960", "5", "0.48", "0.10", "0", "上海Ａ股"],
]


def fixture_bytes(rows: list[list[str]] | None = None) -> bytes:
    lines = ["\t".join(HEADERS), *("\t".join(row) for row in (rows or ROWS))]
    return ("\r\n".join(lines) + "\r\n").encode("gb18030")


class TonghuashunImportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_dir.name) / "test.sqlite3"
        db.init_db()
        trade_db.init_trade_schema()
        self.source_id = trade_services.create_source("交割单测试", "A股")

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_parse_and_import_is_idempotent(self) -> None:
        records = trade_services.parse_tonghuashun_delivery(fixture_bytes())
        self.assertEqual(3, len(records))
        self.assertEqual("2026-08-18 09:30", records[0].trade_at)
        self.assertAlmostEqual(5.10, records[0].fees)
        self.assertEqual("SELL", records[-1].side)
        self.assertEqual(200, records[-1].shares)

        first_result = trade_services.import_tonghuashun_delivery(self.source_id, records)
        self.assertEqual(3, first_result["imported_orders"])
        self.assertEqual(1, first_result["created_ideas"])
        self.assertEqual(1, first_result["created_plans"])

        idea = trade_db.list_ideas(self.source_id)[0]
        self.assertEqual("600545.SS", idea["symbol"])
        self.assertEqual("卓郎智能", idea["name"])
        self.assertEqual("holding", idea["status"])
        plan = trade_db.get_ladder_plan_by_idea(int(idea["id"]))
        levels = trade_db.list_ladder_levels(int(plan["id"]))
        self.assertEqual(1, len(levels))
        self.assertAlmostEqual(4.60, levels[0]["target_price"])
        self.assertAlmostEqual(200, levels[0]["planned_shares"])
        self.assertAlmostEqual(920, levels[0]["planned_amount"])
        self.assertTrue(all(order["ladder_level_id"] == levels[0]["id"] for order in trade_db.list_orders()))

        second_result = trade_services.import_tonghuashun_delivery(self.source_id, records)
        self.assertEqual(0, second_result["imported_orders"])
        self.assertEqual(3, second_result["skipped_orders"])
        self.assertEqual(3, len(trade_db.list_orders()))

    def test_existing_manual_single_level_is_not_overwritten(self) -> None:
        idea_id = trade_services.create_idea(
            self.source_id,
            "600545.SS",
            "卓郎智能",
            "2026-08-18 09:00",
            5.0,
            None,
        )
        trade_services.save_ladder_plan(
            idea_id=idea_id,
            anchor_price=5.0,
            first_shares=300,
            trigger_pct=0,
            levels=[{"level_index": 1, "target_price": 5.0, "planned_shares": 300}],
        )

        records = trade_services.parse_tonghuashun_delivery(fixture_bytes([ROWS[0]]))
        trade_services.import_tonghuashun_delivery(self.source_id, records)

        plan = trade_db.get_ladder_plan_by_idea(idea_id)
        level = trade_db.list_ladder_levels(int(plan["id"]))[0]
        order = trade_db.list_orders(idea_id)[0]
        self.assertAlmostEqual(5.0, level["target_price"])
        self.assertAlmostEqual(300, level["planned_shares"])
        self.assertEqual(level["id"], order["ladder_level_id"])


if __name__ == "__main__":
    unittest.main()
