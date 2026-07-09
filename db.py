from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any


DB_PATH = Path("ladder_buy_manager.sqlite3")


def today_iso() -> str:
    return date.today().isoformat()


def now_minute_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS instruments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                name TEXT,
                category TEXT,
                current_price REAL,
                updated_at TEXT,
                trigger_pct REAL,
                is_active INTEGER DEFAULT 1,
                notes TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS levels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instrument_id INTEGER NOT NULL,
                level_index INTEGER NOT NULL,
                target_price REAL NOT NULL,
                planned_amount REAL NOT NULL,
                executed INTEGER DEFAULT 0,
                executed_at TEXT,
                FOREIGN KEY (instrument_id) REFERENCES instruments(id) ON DELETE CASCADE,
                UNIQUE (instrument_id, level_index)
            )
            """
        )
        ensure_schema(conn)


def ensure_schema(conn: sqlite3.Connection) -> None:
    instrument_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(instruments)").fetchall()
    }
    if "trigger_pct" not in instrument_columns:
        conn.execute("ALTER TABLE instruments ADD COLUMN trigger_pct REAL")
        backfill_trigger_pct(conn)


def backfill_trigger_pct(conn: sqlite3.Connection) -> None:
    instruments = conn.execute("SELECT id FROM instruments").fetchall()
    for instrument in instruments:
        levels = conn.execute(
            """
            SELECT level_index, target_price
            FROM levels
            WHERE instrument_id = ?
              AND level_index IN (1, 2)
            ORDER BY level_index ASC
            """,
            (instrument["id"],),
        ).fetchall()
        if len(levels) < 2:
            continue
        first_price = float(levels[0]["target_price"])
        second_price = float(levels[1]["target_price"])
        if first_price <= 0:
            continue
        conn.execute(
            "UPDATE instruments SET trigger_pct = ? WHERE id = ? AND trigger_pct IS NULL",
            (1 - second_price / first_price, instrument["id"]),
        )


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(query, params).fetchall()


def fetch_one(query: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(query, params).fetchone()


def create_instrument(
    symbol: str,
    name: str = "",
    category: str = "",
    current_price: float | None = None,
    notes: str = "",
    is_active: int = 1,
    trigger_pct: float | None = None,
) -> int:
    updated_at = today_iso() if current_price is not None else None
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO instruments (
                symbol, name, category, current_price, updated_at, trigger_pct, is_active, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol.strip().upper(),
                name.strip(),
                category.strip(),
                current_price,
                updated_at,
                trigger_pct,
                int(is_active),
                notes.strip(),
            ),
        )
        return int(cursor.lastrowid)


def update_instrument(
    instrument_id: int,
    symbol: str,
    name: str,
    category: str,
    current_price: float | None,
    notes: str,
    is_active: int,
    update_price_date: bool = True,
    trigger_pct: float | None = None,
) -> None:
    existing = get_instrument(instrument_id)
    old_price = None if existing is None else existing["current_price"]
    updated_at = existing["updated_at"] if existing is not None else None
    if update_price_date and current_price is not None and current_price != old_price:
        updated_at = today_iso()
    if current_price is None:
        updated_at = None

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE instruments
            SET symbol = ?,
                name = ?,
                category = ?,
                current_price = ?,
                updated_at = ?,
                trigger_pct = COALESCE(?, trigger_pct),
                notes = ?,
                is_active = ?
            WHERE id = ?
            """,
            (
                symbol.strip().upper(),
                name.strip(),
                category.strip(),
                current_price,
                updated_at,
                trigger_pct,
                notes.strip(),
                int(is_active),
                instrument_id,
            ),
        )


def update_current_price(instrument_id: int, current_price: float | None) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE instruments
            SET current_price = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (current_price, today_iso() if current_price is not None else None, instrument_id),
        )


def deactivate_instrument(instrument_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE instruments SET is_active = 0 WHERE id = ?",
            (instrument_id,),
        )


def delete_instrument(instrument_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM instruments WHERE id = ?", (int(instrument_id),))


def get_instrument(instrument_id: int) -> sqlite3.Row | None:
    return fetch_one(
        """
        SELECT id, symbol, name, category, current_price, updated_at, trigger_pct, is_active, notes
        FROM instruments
        WHERE id = ?
        """,
        (instrument_id,),
    )


def get_instrument_by_symbol(symbol: str) -> sqlite3.Row | None:
    return fetch_one(
        """
        SELECT id, symbol, name, category, current_price, updated_at, trigger_pct, is_active, notes
        FROM instruments
        WHERE symbol = ?
        """,
        (symbol.strip().upper(),),
    )


def list_instruments(active_only: bool = False) -> list[sqlite3.Row]:
    where = "WHERE is_active = 1" if active_only else ""
    return fetch_all(
        f"""
        SELECT id, symbol, name, category, current_price, updated_at, trigger_pct, is_active, notes
        FROM instruments
        {where}
        ORDER BY is_active DESC, symbol ASC
        """
    )


def create_level(
    instrument_id: int,
    level_index: int,
    target_price: float,
    planned_amount: float,
    executed: int = 0,
) -> int:
    executed_at = today_iso() if int(executed) == 1 else None
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO levels (
                instrument_id, level_index, target_price, planned_amount, executed, executed_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (instrument_id, level_index, target_price, planned_amount, int(executed), executed_at),
        )
        return int(cursor.lastrowid)


def update_level(
    level_id: int,
    level_index: int,
    target_price: float,
    planned_amount: float,
    executed: int,
) -> None:
    existing = get_level(level_id)
    executed_at = None
    if executed:
        executed_at = existing["executed_at"] if existing and existing["executed"] else today_iso()

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE levels
            SET level_index = ?,
                target_price = ?,
                planned_amount = ?,
                executed = ?,
                executed_at = ?
            WHERE id = ?
            """,
            (level_index, target_price, planned_amount, int(executed), executed_at, level_id),
        )


def delete_level(level_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM levels WHERE id = ?", (level_id,))


def update_level_execution(level_id: int, executed: int, executed_at: str | None) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE levels
            SET executed = ?,
                executed_at = ?
            WHERE id = ?
            """,
            (int(executed), executed_at, int(level_id)),
        )


def get_level(level_id: int) -> sqlite3.Row | None:
    return fetch_one(
        """
        SELECT id, instrument_id, level_index, target_price, planned_amount, executed, executed_at
        FROM levels
        WHERE id = ?
        """,
        (level_id,),
    )


def list_levels(instrument_id: int) -> list[sqlite3.Row]:
    return fetch_all(
        """
        SELECT id, instrument_id, level_index, target_price, planned_amount, executed, executed_at
        FROM levels
        WHERE instrument_id = ?
        ORDER BY level_index ASC
        """,
        (instrument_id,),
    )


def mark_level_executed(level_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE levels
            SET executed = 1,
                executed_at = ?
            WHERE id = ?
            """,
            (today_iso(), level_id),
        )


def undo_level_executed(level_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE levels
            SET executed = 0,
                executed_at = NULL
            WHERE id = ?
            """,
            (level_id,),
        )
