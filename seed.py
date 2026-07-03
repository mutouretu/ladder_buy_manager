import sqlite3

import db


def seed() -> None:
    db.init_db()
    examples = [
        (
            "HSAI",
            "Hesai Group",
            "中概反转",
            13.80,
            [
                (1, 18.00, 5000, 1),
                (2, 14.40, 2500, 0),
                (3, 11.52, 1250, 0),
                (4, 9.22, 625, 0),
                (5, 7.37, 312.50, 0),
            ],
        ),
        (
            "CRM",
            "Salesforce",
            "软件成长",
            245.00,
            [
                (1, 220.00, 3000, 0),
                (2, 198.00, 1500, 0),
                (3, 178.20, 750, 0),
            ],
        ),
        (
            "SGOV",
            "iShares 0-3 Month Treasury Bond ETF",
            "现金池",
            100.35,
            [],
        ),
    ]

    for symbol, name, category, price, levels in examples:
        if db.get_instrument_by_symbol(symbol):
            continue
        instrument_id = db.create_instrument(
            symbol=symbol,
            name=name,
            category=category,
            current_price=price,
        )
        for level_index, target_price, planned_amount, executed in levels:
            level_id = db.create_level(
                instrument_id=instrument_id,
                level_index=level_index,
                target_price=target_price,
                planned_amount=planned_amount,
                executed=executed,
            )
            if executed:
                db.mark_level_executed(level_id)


if __name__ == "__main__":
    try:
        seed()
        print("Seed data inserted.")
    except sqlite3.IntegrityError as exc:
        print(f"Seed failed: {exc}")
