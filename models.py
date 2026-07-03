from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Instrument:
    id: int
    symbol: str
    name: str | None
    category: str | None
    current_price: float | None
    updated_at: str | None
    is_active: int
    notes: str | None


@dataclass(frozen=True)
class Level:
    id: int
    instrument_id: int
    level_index: int
    target_price: float
    planned_amount: float
    executed: int
    executed_at: str | None


@dataclass(frozen=True)
class GeneratedLevel:
    level_index: int
    target_price: float
    planned_shares: int
    planned_amount: float
