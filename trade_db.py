from __future__ import annotations

import sqlite3
from typing import Any

import db


def init_trade_schema() -> None:
    with db.get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trade_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                market TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trade_ideas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT,
                idea_at TEXT NOT NULL,
                idea_price REAL,
                idea_price_at TEXT,
                plan_price REAL,
                current_price REAL,
                status TEXT NOT NULL DEFAULT 'watching',
                completed_at TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (source_id) REFERENCES trade_sources(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trade_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idea_id INTEGER NOT NULL,
                ladder_level_id INTEGER,
                side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
                trade_at TEXT NOT NULL,
                price REAL NOT NULL,
                shares REAL NOT NULL,
                fees REAL NOT NULL DEFAULT 0,
                external_source TEXT,
                external_order_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (idea_id) REFERENCES trade_ideas(id) ON DELETE CASCADE,
                FOREIGN KEY (ladder_level_id) REFERENCES trade_ladder_levels(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trade_ladder_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idea_id INTEGER NOT NULL UNIQUE,
                anchor_price REAL NOT NULL,
                first_shares REAL NOT NULL,
                trigger_pct REAL NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (idea_id) REFERENCES trade_ideas(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trade_ladder_levels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER NOT NULL,
                level_index INTEGER NOT NULL,
                target_price REAL NOT NULL,
                planned_shares REAL NOT NULL,
                planned_amount REAL NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (plan_id) REFERENCES trade_ladder_plans(id) ON DELETE CASCADE,
                UNIQUE (plan_id, level_index)
            )
            """
        )
        ensure_trade_schema(conn)


def create_trade_orders_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE trade_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            idea_id INTEGER NOT NULL,
            ladder_level_id INTEGER,
            side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
            trade_at TEXT NOT NULL,
            price REAL NOT NULL,
            shares REAL NOT NULL,
            fees REAL NOT NULL DEFAULT 0,
            external_source TEXT,
            external_order_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (idea_id) REFERENCES trade_ideas(id) ON DELETE CASCADE,
            FOREIGN KEY (ladder_level_id) REFERENCES trade_ladder_levels(id) ON DELETE SET NULL
        )
        """
    )


def ensure_trade_schema(conn: sqlite3.Connection) -> None:
    idea_columns = {
        row["name"]: row for row in conn.execute("PRAGMA table_info(trade_ideas)").fetchall()
    }
    if idea_columns and idea_columns.get("plan_price") is not None:
        plan_price_column = idea_columns["plan_price"]
        if int(plan_price_column["notnull"]) == 1:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("ALTER TABLE trade_ideas RENAME TO trade_ideas_old")
            conn.execute(
                """
                CREATE TABLE trade_ideas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    name TEXT,
                    idea_at TEXT NOT NULL,
                    idea_price REAL,
                    idea_price_at TEXT,
                    plan_price REAL,
                    current_price REAL,
                    status TEXT NOT NULL DEFAULT 'watching',
                    completed_at TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (source_id) REFERENCES trade_sources(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                INSERT INTO trade_ideas (
                    id, source_id, symbol, name, idea_at, idea_price, idea_price_at,
                    plan_price, current_price,
                    status, completed_at, notes, created_at, updated_at
                )
                SELECT
                    id, source_id, symbol, name, idea_at, NULL, NULL,
                    plan_price, current_price,
                    status, completed_at, notes, created_at, updated_at
                FROM trade_ideas_old
                """
            )
            conn.execute("DROP TABLE trade_ideas_old")
            conn.execute("PRAGMA foreign_keys = ON")
    idea_column_names = {
        row["name"] for row in conn.execute("PRAGMA table_info(trade_ideas)").fetchall()
    }
    if "idea_price" not in idea_column_names:
        conn.execute("ALTER TABLE trade_ideas ADD COLUMN idea_price REAL")
    if "idea_price_at" not in idea_column_names:
        conn.execute("ALTER TABLE trade_ideas ADD COLUMN idea_price_at TEXT")
    ensure_trade_ladder_schema(conn)
    ensure_trade_orders_schema(conn)


def column_type(columns: list[sqlite3.Row], name: str) -> str:
    for column in columns:
        if column["name"] == name:
            return str(column["type"] or "").upper()
    return ""


def create_trade_ladder_plans_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE trade_ladder_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            idea_id INTEGER NOT NULL UNIQUE,
            anchor_price REAL NOT NULL,
            first_shares REAL NOT NULL,
            trigger_pct REAL NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (idea_id) REFERENCES trade_ideas(id) ON DELETE CASCADE
        )
        """
    )


def create_trade_ladder_levels_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE trade_ladder_levels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            level_index INTEGER NOT NULL,
            target_price REAL NOT NULL,
            planned_shares REAL NOT NULL,
            planned_amount REAL NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (plan_id) REFERENCES trade_ladder_plans(id) ON DELETE CASCADE,
            UNIQUE (plan_id, level_index)
        )
        """
    )


def ensure_trade_orders_schema(conn: sqlite3.Connection) -> None:
    order_columns = conn.execute("PRAGMA table_info(trade_orders)").fetchall()
    if not order_columns:
        return
    order_column_names = {row["name"] for row in order_columns}
    if "external_source" not in order_column_names:
        conn.execute("ALTER TABLE trade_orders ADD COLUMN external_source TEXT")
    if "external_order_id" not in order_column_names:
        conn.execute("ALTER TABLE trade_orders ADD COLUMN external_order_id TEXT")
    order_columns = conn.execute("PRAGMA table_info(trade_orders)").fetchall()
    order_column_names = {row["name"] for row in order_columns}
    foreign_keys = conn.execute("PRAGMA foreign_key_list(trade_orders)").fetchall()
    idea_foreign_keys = [row for row in foreign_keys if row["from"] == "idea_id"]
    level_foreign_keys = [row for row in foreign_keys if row["from"] == "ladder_level_id"]
    if (
        "ladder_level_id" in order_column_names
        and column_type(order_columns, "shares") == "REAL"
        and idea_foreign_keys
        and all(row["table"] == "trade_ideas" for row in idea_foreign_keys)
        and level_foreign_keys
        and all(row["table"] == "trade_ladder_levels" for row in level_foreign_keys)
    ):
        create_trade_order_external_index(conn)
        return

    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("DROP TABLE IF EXISTS trade_orders_rebuild_old")
    conn.execute("ALTER TABLE trade_orders RENAME TO trade_orders_rebuild_old")
    create_trade_orders_table(conn)
    if "ladder_level_id" in order_column_names:
        conn.execute(
            """
            INSERT INTO trade_orders (
                id, idea_id, ladder_level_id, side, trade_at, price, shares, fees,
                external_source, external_order_id, created_at, updated_at
            )
            SELECT
                id, idea_id, ladder_level_id, side, trade_at, price, shares, fees,
                external_source, external_order_id, created_at, updated_at
            FROM trade_orders_rebuild_old
            """
        )
    else:
        conn.execute(
            """
            INSERT INTO trade_orders (
                id, idea_id, ladder_level_id, side, trade_at, price, shares, fees,
                external_source, external_order_id, created_at, updated_at
            )
            SELECT
                id, idea_id, NULL, side, trade_at, price, shares, fees,
                external_source, external_order_id, created_at, updated_at
            FROM trade_orders_rebuild_old
            """
        )
    conn.execute("DROP TABLE trade_orders_rebuild_old")
    conn.execute("PRAGMA foreign_keys = ON")
    create_trade_order_external_index(conn)


def create_trade_order_external_index(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_trade_orders_external
        ON trade_orders (external_source, external_order_id)
        WHERE external_source IS NOT NULL AND external_order_id IS NOT NULL
        """
    )


def ensure_trade_ladder_schema(conn: sqlite3.Connection) -> None:
    plan_columns = conn.execute("PRAGMA table_info(trade_ladder_plans)").fetchall()
    if plan_columns and column_type(plan_columns, "first_shares") != "REAL":
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("DROP TABLE IF EXISTS trade_ladder_plans_rebuild_old")
        conn.execute("ALTER TABLE trade_ladder_plans RENAME TO trade_ladder_plans_rebuild_old")
        create_trade_ladder_plans_table(conn)
        conn.execute(
            """
            INSERT INTO trade_ladder_plans (
                id, idea_id, anchor_price, first_shares, trigger_pct, created_at, updated_at
            )
            SELECT
                id, idea_id, anchor_price, CAST(first_shares AS REAL),
                trigger_pct, created_at, updated_at
            FROM trade_ladder_plans_rebuild_old
            """
        )
        conn.execute("DROP TABLE trade_ladder_plans_rebuild_old")
        conn.execute("PRAGMA foreign_keys = ON")

    level_columns = conn.execute("PRAGMA table_info(trade_ladder_levels)").fetchall()
    if level_columns and column_type(level_columns, "planned_shares") != "REAL":
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("DROP TABLE IF EXISTS trade_ladder_levels_rebuild_old")
        conn.execute("ALTER TABLE trade_ladder_levels RENAME TO trade_ladder_levels_rebuild_old")
        create_trade_ladder_levels_table(conn)
        conn.execute(
            """
            INSERT INTO trade_ladder_levels (
                id, plan_id, level_index, target_price, planned_shares,
                planned_amount, created_at, updated_at
            )
            SELECT
                id, plan_id, level_index, target_price, CAST(planned_shares AS REAL),
                planned_amount, created_at, updated_at
            FROM trade_ladder_levels_rebuild_old
            """
        )
        conn.execute("DROP TABLE trade_ladder_levels_rebuild_old")
        conn.execute("PRAGMA foreign_keys = ON")


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    return db.fetch_all(query, params)


def fetch_one(query: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    return db.fetch_one(query, params)


def create_source(name: str, market: str, is_active: int = 1) -> int:
    now = db.today_iso()
    with db.get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO trade_sources (name, market, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name.strip(), market.strip(), int(is_active), now, now),
        )
        return int(cursor.lastrowid)


def update_source(source_id: int, name: str, market: str, is_active: int = 1) -> None:
    existing = get_source(source_id)
    with db.get_connection() as conn:
        conn.execute(
            """
            UPDATE trade_sources
            SET name = ?,
                market = ?,
                is_active = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (name.strip(), market.strip(), int(is_active), db.today_iso(), int(source_id)),
        )
        if existing is not None and str(existing["market"]).strip() != market.strip():
            conn.execute(
                """
                UPDATE trade_ideas
                SET idea_price = NULL,
                    idea_price_at = NULL,
                    updated_at = ?
                WHERE source_id = ?
                """,
                (db.today_iso(), int(source_id)),
            )


def delete_source(source_id: int) -> None:
    with db.get_connection() as conn:
        conn.execute("DELETE FROM trade_sources WHERE id = ?", (int(source_id),))


def get_source(source_id: int) -> sqlite3.Row | None:
    return fetch_one(
        """
        SELECT id, name, market, is_active, created_at, updated_at
        FROM trade_sources
        WHERE id = ?
        """,
        (int(source_id),),
    )


def get_source_by_name(name: str) -> sqlite3.Row | None:
    return fetch_one(
        """
        SELECT id, name, market, is_active, created_at, updated_at
        FROM trade_sources
        WHERE name = ?
        """,
        (name.strip(),),
    )


def list_sources(active_only: bool = True) -> list[sqlite3.Row]:
    where = "WHERE is_active = 1" if active_only else ""
    return fetch_all(
        f"""
        SELECT id, name, market, is_active, created_at, updated_at
        FROM trade_sources
        {where}
        ORDER BY name ASC
        """
    )


def create_idea(
    source_id: int,
    symbol: str,
    name: str,
    idea_at: str,
    plan_price: float | None,
    current_price: float | None,
    status: str = "watching",
    notes: str = "",
) -> int:
    now = db.today_iso()
    with db.get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO trade_ideas (
                source_id, symbol, name, idea_at, plan_price, current_price,
                status, completed_at, notes, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(source_id),
                symbol.strip().upper(),
                name.strip(),
                idea_at.strip(),
                plan_price,
                current_price,
                status,
                now if status == "completed" else None,
                notes.strip(),
                now,
                now,
            ),
        )
        return int(cursor.lastrowid)


def update_idea(
    idea_id: int,
    symbol: str,
    name: str,
    idea_at: str,
    plan_price: float | None,
    current_price: float | None,
    status: str | None = None,
    notes: str | None = None,
) -> None:
    existing = get_idea(idea_id)
    if existing is None:
        return
    next_status = status if status is not None else existing["status"]
    completed_at = existing["completed_at"]
    if next_status == "completed" and completed_at is None:
        completed_at = db.today_iso()
    if next_status != "completed":
        completed_at = None
    next_notes = existing["notes"] if notes is None else notes.strip()
    cleaned_symbol = symbol.strip().upper()
    cleaned_idea_at = idea_at.strip()
    historical_identity_changed = (
        cleaned_symbol != str(existing["symbol"]).strip().upper()
        or cleaned_idea_at != str(existing["idea_at"]).strip()
    )
    idea_price = None if historical_identity_changed else existing["idea_price"]
    idea_price_at = None if historical_identity_changed else existing["idea_price_at"]
    with db.get_connection() as conn:
        conn.execute(
            """
            UPDATE trade_ideas
            SET symbol = ?,
                name = ?,
                idea_at = ?,
                idea_price = ?,
                idea_price_at = ?,
                plan_price = ?,
                current_price = ?,
                status = ?,
                completed_at = ?,
                notes = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                cleaned_symbol,
                name.strip(),
                cleaned_idea_at,
                idea_price,
                idea_price_at,
                plan_price,
                current_price,
                next_status,
                completed_at,
                next_notes,
                db.today_iso(),
                int(idea_id),
            ),
        )


def update_idea_status(idea_id: int, status: str) -> None:
    existing = get_idea(idea_id)
    if existing is None:
        return
    completed_at = db.today_iso() if status == "completed" else None
    with db.get_connection() as conn:
        conn.execute(
            """
            UPDATE trade_ideas
            SET status = ?,
                completed_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (status, completed_at, db.today_iso(), int(idea_id)),
        )


def update_idea_current_price(idea_id: int, current_price: float | None) -> None:
    with db.get_connection() as conn:
        conn.execute(
            """
            UPDATE trade_ideas
            SET current_price = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (current_price, db.today_iso(), int(idea_id)),
        )


def update_idea_symbol(idea_id: int, symbol: str) -> None:
    with db.get_connection() as conn:
        conn.execute(
            """
            UPDATE trade_ideas
            SET symbol = ?,
                updated_at = ?
            WHERE id = ?
              AND symbol <> ?
            """,
            (
                symbol.strip().upper(),
                db.today_iso(),
                int(idea_id),
                symbol.strip().upper(),
            ),
        )


def update_idea_name_if_empty(idea_id: int, name: str) -> None:
    cleaned_name = name.strip()
    if not cleaned_name:
        return
    with db.get_connection() as conn:
        conn.execute(
            """
            UPDATE trade_ideas
            SET name = ?,
                updated_at = ?
            WHERE id = ?
              AND (name IS NULL OR TRIM(name) = '')
            """,
            (cleaned_name, db.today_iso(), int(idea_id)),
        )


def update_idea_historical_price(
    idea_id: int,
    idea_price: float,
    idea_price_at: str,
) -> None:
    with db.get_connection() as conn:
        conn.execute(
            """
            UPDATE trade_ideas
            SET idea_price = ?,
                idea_price_at = ?,
                updated_at = ?
            WHERE id = ?
              AND idea_price IS NULL
            """,
            (float(idea_price), idea_price_at.strip(), db.today_iso(), int(idea_id)),
        )


def update_idea_plan_price(idea_id: int, plan_price: float | None) -> None:
    with db.get_connection() as conn:
        conn.execute(
            """
            UPDATE trade_ideas
            SET plan_price = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (plan_price, db.today_iso(), int(idea_id)),
        )


def delete_idea(idea_id: int) -> None:
    with db.get_connection() as conn:
        conn.execute("DELETE FROM trade_ideas WHERE id = ?", (int(idea_id),))


def get_idea(idea_id: int) -> sqlite3.Row | None:
    return fetch_one(
        """
        SELECT
            id, source_id, symbol, name, idea_at, idea_price, idea_price_at,
            plan_price, current_price,
            status, completed_at, notes, created_at, updated_at
        FROM trade_ideas
        WHERE id = ?
        """,
        (int(idea_id),),
    )


def list_ideas(source_id: int | None = None) -> list[sqlite3.Row]:
    if source_id is None:
        return fetch_all(
            """
            SELECT
                id, source_id, symbol, name, idea_at, idea_price, idea_price_at,
                plan_price, current_price,
                status, completed_at, notes, created_at, updated_at
            FROM trade_ideas
            ORDER BY idea_at DESC, symbol ASC
            """
        )
    return fetch_all(
        """
        SELECT
            id, source_id, symbol, name, idea_at, idea_price, idea_price_at,
            plan_price, current_price,
            status, completed_at, notes, created_at, updated_at
        FROM trade_ideas
        WHERE source_id = ?
        ORDER BY idea_at DESC, symbol ASC
        """,
        (int(source_id),),
    )


def create_order(
    idea_id: int,
    side: str,
    trade_at: str,
    price: float,
    shares: float,
    fees: float = 0.0,
    ladder_level_id: int | None = None,
    external_source: str | None = None,
    external_order_id: str | None = None,
) -> int:
    now = db.today_iso()
    with db.get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO trade_orders (
                idea_id, ladder_level_id, side, trade_at, price, shares, fees,
                external_source, external_order_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(idea_id),
                int(ladder_level_id) if ladder_level_id is not None else None,
                side.strip().upper(),
                trade_at.strip(),
                float(price),
                float(shares),
                float(fees),
                external_source.strip() if external_source else None,
                external_order_id.strip() if external_order_id else None,
                now,
                now,
            ),
        )
        return int(cursor.lastrowid)


def update_order(
    order_id: int,
    side: str,
    trade_at: str,
    price: float,
    shares: float,
    fees: float = 0.0,
    ladder_level_id: int | None = None,
) -> None:
    with db.get_connection() as conn:
        conn.execute(
            """
            UPDATE trade_orders
            SET side = ?,
                ladder_level_id = ?,
                trade_at = ?,
                price = ?,
                shares = ?,
                fees = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                side.strip().upper(),
                int(ladder_level_id) if ladder_level_id is not None else None,
                trade_at.strip(),
                float(price),
                float(shares),
                float(fees),
                db.today_iso(),
                int(order_id),
            ),
        )


def delete_order(order_id: int) -> None:
    with db.get_connection() as conn:
        conn.execute("DELETE FROM trade_orders WHERE id = ?", (int(order_id),))


def get_order(order_id: int) -> sqlite3.Row | None:
    return fetch_one(
        """
        SELECT
            id, idea_id, ladder_level_id, side, trade_at, price, shares, fees,
            external_source, external_order_id, created_at, updated_at
        FROM trade_orders
        WHERE id = ?
        """,
        (int(order_id),),
    )


def list_orders(idea_id: int | None = None) -> list[sqlite3.Row]:
    if idea_id is None:
        return fetch_all(
            """
            SELECT
                id, idea_id, ladder_level_id, side, trade_at, price, shares, fees,
                external_source, external_order_id, created_at, updated_at
            FROM trade_orders
            ORDER BY trade_at ASC, id ASC
            """
        )
    return fetch_all(
        """
        SELECT
            id, idea_id, ladder_level_id, side, trade_at, price, shares, fees,
            external_source, external_order_id, created_at, updated_at
        FROM trade_orders
        WHERE idea_id = ?
        ORDER BY trade_at ASC, id ASC
        """,
        (int(idea_id),),
    )


def import_external_orders(
    source_id: int,
    records: list[dict[str, Any]],
    external_source: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "created_ideas": 0,
        "created_plans": 0,
        "imported_orders": 0,
        "skipped_orders": 0,
        "incomplete_symbols": [],
        "plan_conflicts": [],
    }
    if not records:
        return result

    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(str(record["symbol"]), []).append(record)

    now = db.today_iso()
    with db.get_connection() as conn:
        source = conn.execute(
            "SELECT id FROM trade_sources WHERE id = ?",
            (int(source_id),),
        ).fetchone()
        if source is None:
            raise ValueError("项目不存在。")

        existing_external_ids = {
            str(row["external_order_id"])
            for row in conn.execute(
                """
                SELECT external_order_id
                FROM trade_orders
                WHERE external_source = ?
                  AND external_order_id IS NOT NULL
                """,
                (external_source,),
            ).fetchall()
        }

        for symbol, symbol_records in grouped.items():
            pending_records = [
                record
                for record in symbol_records
                if str(record["external_order_id"]) not in existing_external_ids
            ]
            result["skipped_orders"] += len(symbol_records) - len(pending_records)
            if not pending_records:
                continue

            raw_symbol = str(pending_records[0].get("raw_symbol") or symbol)
            idea = conn.execute(
                """
                SELECT DISTINCT i.*
                FROM trade_ideas i
                JOIN trade_orders o ON o.idea_id = i.id
                WHERE i.source_id = ?
                  AND i.symbol IN (?, ?)
                  AND o.external_source = ?
                ORDER BY i.id DESC
                LIMIT 1
                """,
                (int(source_id), symbol, raw_symbol, external_source),
            ).fetchone()
            imported_idea = idea is not None
            if idea is None:
                idea = conn.execute(
                    """
                    SELECT *
                    FROM trade_ideas
                    WHERE source_id = ?
                      AND symbol IN (?, ?)
                      AND status <> 'completed'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (int(source_id), symbol, raw_symbol),
                ).fetchone()

            earliest_trade_at = min(str(record["trade_at"]) for record in pending_records)
            name = next(
                (str(record.get("name") or "").strip() for record in pending_records if record.get("name")),
                "",
            )
            if idea is None:
                cursor = conn.execute(
                    """
                    INSERT INTO trade_ideas (
                        source_id, symbol, name, idea_at, plan_price, current_price,
                        status, completed_at, notes, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, NULL, NULL, 'watching', NULL, '', ?, ?)
                    """,
                    (int(source_id), symbol, name, earliest_trade_at, now, now),
                )
                idea_id = int(cursor.lastrowid)
                result["created_ideas"] += 1
            else:
                idea_id = int(idea["id"])
                if imported_idea and earliest_trade_at < str(idea["idea_at"]):
                    conn.execute(
                        """
                        UPDATE trade_ideas
                        SET idea_at = ?, idea_price = NULL, idea_price_at = NULL, updated_at = ?
                        WHERE id = ?
                        """,
                        (earliest_trade_at, now, idea_id),
                    )
                if name:
                    conn.execute(
                        """
                        UPDATE trade_ideas
                        SET name = CASE WHEN name IS NULL OR TRIM(name) = '' THEN ? ELSE name END,
                            symbol = ?,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (name, symbol, now, idea_id),
                    )

            plan = conn.execute(
                "SELECT * FROM trade_ladder_plans WHERE idea_id = ?",
                (idea_id,),
            ).fetchone()
            level_id: int | None = None
            manage_imported_plan = False
            if plan is None and any(record["side"] == "BUY" for record in pending_records):
                buy_records = [record for record in pending_records if record["side"] == "BUY"]
                buy_shares = sum(float(record["shares"]) for record in buy_records)
                buy_amount = sum(float(record["price"]) * float(record["shares"]) for record in buy_records)
                anchor_price = buy_amount / buy_shares
                plan_cursor = conn.execute(
                    """
                    INSERT INTO trade_ladder_plans (
                        idea_id, anchor_price, first_shares, trigger_pct, created_at, updated_at
                    )
                    VALUES (?, ?, ?, 0, ?, ?)
                    """,
                    (idea_id, anchor_price, buy_shares, now, now),
                )
                plan_id = int(plan_cursor.lastrowid)
                level_cursor = conn.execute(
                    """
                    INSERT INTO trade_ladder_levels (
                        plan_id, level_index, target_price, planned_shares,
                        planned_amount, created_at, updated_at
                    )
                    VALUES (?, 1, ?, ?, ?, ?, ?)
                    """,
                    (plan_id, anchor_price, buy_shares, round(buy_amount, 2), now, now),
                )
                level_id = int(level_cursor.lastrowid)
                manage_imported_plan = True
                result["created_plans"] += 1
            elif plan is not None:
                levels = conn.execute(
                    """
                    SELECT id
                    FROM trade_ladder_levels
                    WHERE plan_id = ?
                    ORDER BY level_index ASC
                    """,
                    (int(plan["id"]),),
                ).fetchall()
                if len(levels) == 1:
                    level_id = int(levels[0]["id"])
                    manage_imported_plan = imported_idea and float(plan["trigger_pct"]) == 0
                elif any(record["side"] == "BUY" for record in pending_records):
                    result["plan_conflicts"].append(symbol)

            if level_id is not None:
                conn.execute(
                    """
                    UPDATE trade_orders
                    SET ladder_level_id = ?, updated_at = ?
                    WHERE idea_id = ?
                      AND external_source = ?
                      AND ladder_level_id IS NULL
                    """,
                    (level_id, now, idea_id, external_source),
                )

            for record in pending_records:
                try:
                    conn.execute(
                        """
                        INSERT INTO trade_orders (
                            idea_id, ladder_level_id, side, trade_at, price, shares, fees,
                            external_source, external_order_id, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            idea_id,
                            level_id,
                            str(record["side"]),
                            str(record["trade_at"]),
                            float(record["price"]),
                            float(record["shares"]),
                            float(record["fees"]),
                            external_source,
                            str(record["external_order_id"]),
                            now,
                            now,
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    if "trade_orders.external_source, trade_orders.external_order_id" not in str(exc):
                        raise
                    result["skipped_orders"] += 1
                    continue
                existing_external_ids.add(str(record["external_order_id"]))
                result["imported_orders"] += 1

            if level_id is not None and manage_imported_plan:
                executed_buys = conn.execute(
                    """
                    SELECT COALESCE(SUM(price * shares), 0) AS amount,
                           COALESCE(SUM(shares), 0) AS shares
                    FROM trade_orders
                    WHERE ladder_level_id = ? AND side = 'BUY'
                    """,
                    (level_id,),
                ).fetchone()
                executed_shares = float(executed_buys["shares"])
                if executed_shares > 0:
                    executed_amount = float(executed_buys["amount"])
                    average_price = executed_amount / executed_shares
                    level = conn.execute(
                        "SELECT plan_id FROM trade_ladder_levels WHERE id = ?",
                        (level_id,),
                    ).fetchone()
                    conn.execute(
                        """
                        UPDATE trade_ladder_levels
                        SET target_price = ?, planned_shares = ?, planned_amount = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (average_price, executed_shares, round(executed_amount, 2), now, level_id),
                    )
                    conn.execute(
                        """
                        UPDATE trade_ladder_plans
                        SET anchor_price = ?, first_shares = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (average_price, executed_shares, now, int(level["plan_id"])),
                    )

            totals = conn.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN side = 'BUY' THEN shares ELSE 0 END), 0) AS bought,
                    COALESCE(SUM(CASE WHEN side = 'SELL' THEN shares ELSE 0 END), 0) AS sold
                FROM trade_orders
                WHERE idea_id = ?
                """,
                (idea_id,),
            ).fetchone()
            bought_shares = float(totals["bought"])
            sold_shares = float(totals["sold"])
            next_status = "holding" if bought_shares > 0 else "watching"
            conn.execute(
                """
                UPDATE trade_ideas
                SET status = ?, completed_at = NULL, updated_at = ?
                WHERE id = ?
                """,
                (next_status, now, idea_id),
            )
            if level_id is not None:
                conn.execute(
                    "UPDATE trade_ideas SET plan_price = NULL, updated_at = ? WHERE id = ?",
                    (now, idea_id),
                )
            if sold_shares - bought_shares > 0.00000001:
                result["incomplete_symbols"].append(symbol)

    result["incomplete_symbols"] = sorted(set(result["incomplete_symbols"]))
    result["plan_conflicts"] = sorted(set(result["plan_conflicts"]))
    return result


def get_ladder_plan_by_idea(idea_id: int) -> sqlite3.Row | None:
    return fetch_one(
        """
        SELECT id, idea_id, anchor_price, first_shares, trigger_pct, created_at, updated_at
        FROM trade_ladder_plans
        WHERE idea_id = ?
        """,
        (int(idea_id),),
    )


def get_ladder_plan(plan_id: int) -> sqlite3.Row | None:
    return fetch_one(
        """
        SELECT id, idea_id, anchor_price, first_shares, trigger_pct, created_at, updated_at
        FROM trade_ladder_plans
        WHERE id = ?
        """,
        (int(plan_id),),
    )


def get_ladder_level(level_id: int) -> sqlite3.Row | None:
    return fetch_one(
        """
        SELECT
            id, plan_id, level_index, target_price, planned_shares,
            planned_amount, created_at, updated_at
        FROM trade_ladder_levels
        WHERE id = ?
        """,
        (int(level_id),),
    )


def list_ladder_levels(plan_id: int) -> list[sqlite3.Row]:
    return fetch_all(
        """
        SELECT
            id, plan_id, level_index, target_price, planned_shares,
            planned_amount, created_at, updated_at
        FROM trade_ladder_levels
        WHERE plan_id = ?
        ORDER BY level_index ASC
        """,
        (int(plan_id),),
    )


def replace_ladder_plan(
    idea_id: int,
    anchor_price: float,
    first_shares: float,
    trigger_pct: float,
    levels: list[dict],
) -> int:
    now = db.today_iso()
    with db.get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM trade_ladder_plans WHERE idea_id = ?",
            (int(idea_id),),
        ).fetchone()
        if existing is None:
            cursor = conn.execute(
                """
                INSERT INTO trade_ladder_plans (
                    idea_id, anchor_price, first_shares, trigger_pct, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (int(idea_id), float(anchor_price), float(first_shares), float(trigger_pct), now, now),
            )
            plan_id = int(cursor.lastrowid)
        else:
            plan_id = int(existing["id"])
            conn.execute(
                """
                UPDATE trade_ladder_plans
                SET anchor_price = ?,
                    first_shares = ?,
                    trigger_pct = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (float(anchor_price), float(first_shares), float(trigger_pct), now, plan_id),
            )

        existing_levels = {
            int(row["level_index"]): row
            for row in conn.execute(
                """
                SELECT id, level_index
                FROM trade_ladder_levels
                WHERE plan_id = ?
                """,
                (plan_id,),
            ).fetchall()
        }
        incoming_indexes = {int(level["level_index"]) for level in levels}
        for level in levels:
            level_index = int(level["level_index"])
            if level_index in existing_levels:
                conn.execute(
                    """
                    UPDATE trade_ladder_levels
                    SET target_price = ?,
                        planned_shares = ?,
                        planned_amount = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        float(level["target_price"]),
                        float(level["planned_shares"]),
                        float(level["planned_amount"]),
                        now,
                        int(existing_levels[level_index]["id"]),
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO trade_ladder_levels (
                        plan_id, level_index, target_price, planned_shares,
                        planned_amount, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        plan_id,
                        level_index,
                        float(level["target_price"]),
                        float(level["planned_shares"]),
                        float(level["planned_amount"]),
                        now,
                        now,
                    ),
                )
        for level_index, row in existing_levels.items():
            if level_index not in incoming_indexes:
                conn.execute("DELETE FROM trade_ladder_levels WHERE id = ?", (int(row["id"]),))
        return plan_id


def delete_ladder_plan(idea_id: int) -> None:
    with db.get_connection() as conn:
        conn.execute("DELETE FROM trade_ladder_plans WHERE idea_id = ?", (int(idea_id),))
