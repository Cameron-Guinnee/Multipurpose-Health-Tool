"""Log manager: monthly log file I/O and daily entry helpers.

Storage layout:
    src/data/logs/YYYY-MM.json

Each file is a dict keyed by ISO date string (YYYY-MM-DD). Each day holds
lists of typed entries. All numeric values are stored in metric units;
the display layer handles conversion.

Entry types per day:
    food_entries        – individual food items, optionally categorised by meal
    water_entries       – incremental water intake
    weight_entries      – one or more weigh-ins
    exercise_entries    – activity / workout records
    biometric_entries   – blood pressure and other biometrics
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from core.console_manager import cprint  # type: ignore
except Exception:
    def cprint(msg: str) -> None:  # type: ignore
        print(msg)

from core.data_manager import BASE_DIR, iso_now


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
LOGS_DIR = BASE_DIR / "data" / "logs"


def _log_path(year: int, month: int) -> Path:
    return LOGS_DIR / f"{year:04d}-{month:02d}.json"


def log_path_for_date(d: date) -> Path:
    return _log_path(d.year, d.month)


# ---------------------------------------------------------------------------
# Empty-entry factories
# ---------------------------------------------------------------------------
def _empty_day() -> Dict[str, List[Any]]:
    return {
        "food_entries": [],
        "water_entries": [],
        "weight_entries": [],
        "exercise_entries": [],
        "biometric_entries": [],
    }


def make_food_entry(
    name: str,
    calories: float,
    protein_g: float = 0.0,
    carbs_g: float = 0.0,
    fat_g: float = 0.0,
    quantity: float = 1.0,
    unit: str = "serving",
    meal_category: str = "uncategorized",
) -> Dict[str, Any]:
    return {
        "id": uuid.uuid4().hex[:6],
        "logged_at": iso_now(),
        "meal_category": meal_category.strip().lower(),
        "name": name.strip(),
        "quantity": quantity,
        "unit": unit.strip(),
        "calories": round(calories, 1),
        "protein_g": round(protein_g, 1),
        "carbs_g": round(carbs_g, 1),
        "fat_g": round(fat_g, 1),
    }


def make_water_entry(amount_ml: float) -> Dict[str, Any]:
    return {
        "logged_at": iso_now(),
        "amount_ml": round(amount_ml, 1),
    }


def make_weight_entry(weight_kg: float, notes: str = "") -> Dict[str, Any]:
    return {
        "logged_at": iso_now(),
        "weight_kg": round(weight_kg, 4),
        "notes": notes.strip(),
    }


def make_exercise_entry(
    name: str,
    duration_minutes: int = 0,
    calories_burned: float = 0.0,
    notes: str = "",
) -> Dict[str, Any]:
    return {
        "logged_at": iso_now(),
        "name": name.strip(),
        "duration_minutes": duration_minutes,
        "calories_burned": round(calories_burned, 1),
        "notes": notes.strip(),
    }


def make_blood_pressure_entry(
    systolic_mmhg: int,
    diastolic_mmhg: int,
    pulse_bpm: Optional[int] = None,
    notes: str = "",
) -> Dict[str, Any]:
    return {
        "logged_at": iso_now(),
        "type": "blood_pressure",
        "systolic_mmhg": systolic_mmhg,
        "diastolic_mmhg": diastolic_mmhg,
        "pulse_bpm": pulse_bpm,
        "notes": notes.strip(),
    }


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------
def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    os.replace(tmp, path)


def load_month(year: int, month: int) -> Dict[str, Dict[str, List[Any]]]:
    """Load a monthly log file, returning an empty dict if it doesn't exist."""
    path = _log_path(year, month)
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Unexpected format")
        return data
    except (json.JSONDecodeError, ValueError):
        backup = path.with_name(
            f"{path.stem}.corrupt-{datetime.now().strftime('%Y%m%d-%H%M%S')}{path.suffix}"
        )
        try:
            os.replace(path, backup)
            cprint(f"[yellow][!] {path.name} was corrupted. Backed up to {backup.name}.[/yellow]")
        except OSError:
            pass
        return {}


def save_month(year: int, month: int, data: Dict[str, Any]) -> None:
    _atomic_write_json(_log_path(year, month), data)


def load_day(d: date) -> Dict[str, List[Any]]:
    """Return the entry dict for a specific date, merging against an empty day."""
    month_data = load_month(d.year, d.month)
    key = d.isoformat()
    day = month_data.get(key, {})
    # Merge so any new entry-type keys are always present
    merged = _empty_day()
    merged.update(day)
    return merged


def save_day(d: date, day_data: Dict[str, List[Any]]) -> None:
    """Write a single day back into its monthly file."""
    month_data = load_month(d.year, d.month)
    month_data[d.isoformat()] = day_data
    save_month(d.year, d.month, month_data)


# ---------------------------------------------------------------------------
# Mutation helpers  (load → mutate → save in one call)
# ---------------------------------------------------------------------------
def append_entry(d: date, entry_type: str, entry: Dict[str, Any]) -> None:
    """Append a single entry to a day's list and persist immediately."""
    day = load_day(d)
    if entry_type not in day:
        day[entry_type] = []
    day[entry_type].append(entry)
    save_day(d, day)


def delete_entry(d: date, entry_type: str, entry_id: str) -> bool:
    """Delete a food entry by id. Returns True if found and removed."""
    day = load_day(d)
    entries = day.get(entry_type, [])
    original_len = len(entries)
    day[entry_type] = [e for e in entries if e.get("id") != entry_id]
    if len(day[entry_type]) < original_len:
        save_day(d, day)
        return True
    return False


# ---------------------------------------------------------------------------
# Daily aggregates  (used by dashboard)
# ---------------------------------------------------------------------------
def get_daily_totals(d: date) -> Dict[str, float]:
    """Return summed nutrition and water totals for a given date."""
    day = load_day(d)

    calories = sum(e.get("calories", 0.0) for e in day["food_entries"])
    protein_g = sum(e.get("protein_g", 0.0) for e in day["food_entries"])
    carbs_g = sum(e.get("carbs_g", 0.0) for e in day["food_entries"])
    fat_g = sum(e.get("fat_g", 0.0) for e in day["food_entries"])
    water_ml = sum(e.get("amount_ml", 0.0) for e in day["water_entries"])

    return {
        "calories": round(calories, 1),
        "protein_g": round(protein_g, 1),
        "carbs_g": round(carbs_g, 1),
        "fat_g": round(fat_g, 1),
        "water_ml": round(water_ml, 1),
    }


def get_latest_weight(d: date) -> Optional[float]:
    """Return the most recent weight_kg logged on a given date, or None."""
    day = load_day(d)
    entries = day.get("weight_entries", [])
    if not entries:
        return None
    latest = max(entries, key=lambda e: e.get("logged_at", ""))
    return latest.get("weight_kg")


# ---------------------------------------------------------------------------
# Multi-day queries  (for trend analysis)
# ---------------------------------------------------------------------------
def load_date_range(
    start: date, end: date
) -> Dict[str, Dict[str, List[Any]]]:
    """Load all daily entries between start and end (inclusive).

    Iterates over the months spanned, loading each monthly file once.
    Returns a flat dict keyed by ISO date string.
    """
    # Collect the unique (year, month) pairs we need
    months_needed: set[tuple[int, int]] = set()
    current = date(start.year, start.month, 1)
    while current <= end:
        months_needed.add((current.year, current.month))
        # Advance to next month
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    # Load each month once
    all_days: Dict[str, Dict[str, List[Any]]] = {}
    for year, month in sorted(months_needed):
        month_data = load_month(year, month)
        all_days.update(month_data)

    # Filter to the exact date range requested
    start_str = start.isoformat()
    end_str = end.isoformat()
    return {k: v for k, v in all_days.items() if start_str <= k <= end_str}