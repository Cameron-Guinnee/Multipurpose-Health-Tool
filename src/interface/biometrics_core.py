"""
biometrics_core.py
──────────────────
Shared constants, persistence helpers, and unit-conversion utilities for
the biometrics subsystem.

Kept in its own module so that both menu_biometrics and
menu_biometrics_trends can import from here without creating a circular
dependency between each other.
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any, Dict, List, Tuple

from core.data_manager import DATA_DIR, _atomic_write_json

# ---------------------------------------------------------------------------
# Path
# ---------------------------------------------------------------------------

BIOMETRICS_PATH = DATA_DIR / "biometrics.json"

# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------

# Ordered list of supported metric types with display metadata.
# Each entry: (key, label, unit_metric, unit_imperial, description)
# Values are ALWAYS stored in the metric (SI) unit.
_METRIC_DEFS: List[tuple] = [
    ("weight",        "Weight",          "kg",    "lbs",  None),
    ("bp_systolic",   "Blood Pressure",  "mmHg",  "mmHg", "systolic"),
    ("bp_diastolic",  "Blood Pressure",  "mmHg",  "mmHg", "diastolic"),
    ("heart_rate",    "Heart Rate",      "bpm",   "bpm",  None),
    ("waist",         "Waist",           "cm",    "in",   None),
    ("body_fat_pct",  "Body Fat %",      "%",     "%",    None),
]

# Metrics displayed as a pair (rendered on one row in the log table).
_BP_PAIR = ("bp_systolic", "bp_diastolic")

# Rich colour style per metric (used in the log table and trend header).
_METRIC_STYLE: Dict[str, str] = {
    "weight":       "cyan",
    "bp_systolic":  "red",
    "bp_diastolic": "red",
    "heart_rate":   "magenta",
    "waist":        "yellow",
    "body_fat_pct": "green",
}

# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _load_biometrics() -> Dict[str, Any]:
    """Return the full biometrics store: {"entries": [...]}."""
    if not BIOMETRICS_PATH.exists():
        return {"entries": []}
    try:
        with BIOMETRICS_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data.get("entries"), list):
            data["entries"] = []
        return data
    except (json.JSONDecodeError, OSError):
        return {"entries": []}


def _save_biometrics(data: Dict[str, Any]) -> None:
    _atomic_write_json(BIOMETRICS_PATH, data)


def _entries_for_date(d: date) -> List[Dict[str, Any]]:
    """Return all biometric entries logged on *d*."""
    ds = d.isoformat()
    return [e for e in _load_biometrics().get("entries", []) if e.get("date") == ds]


def _make_entry(metric: str, value: float, d: date, note: str = "") -> Dict[str, Any]:
    return {
        "id":     uuid.uuid4().hex[:8],
        "date":   d.isoformat(),
        "metric": metric,
        "value":  round(value, 2),
        "note":   note.strip(),
    }


def _append_biometric_entry(entry: Dict[str, Any]) -> None:
    data = _load_biometrics()
    data["entries"].append(entry)
    _save_biometrics(data)


def _delete_biometric_entry(entry_id: str) -> bool:
    data = _load_biometrics()
    before = len(data["entries"])
    data["entries"] = [e for e in data["entries"] if e.get("id") != entry_id]
    if len(data["entries"]) < before:
        _save_biometrics(data)
        return True
    return False

# ---------------------------------------------------------------------------
# Unit conversion / display helpers
# ---------------------------------------------------------------------------

def _metric_label_unit(metric: str, units: str) -> Tuple[str, str]:
    """Return (display_label, display_unit) for a given metric key."""
    for key, label, u_metric, u_imperial, _ in _METRIC_DEFS:
        if key == metric:
            return label, (u_imperial if units == "imperial" else u_metric)
    return metric.replace("_", " ").title(), ""


def _to_display(stored_value: float, metric: str, units: str) -> float:
    """Convert a stored (metric/SI) value to the user's preferred display unit."""
    if units != "imperial":
        return stored_value
    if metric == "weight":
        return round(stored_value * 2.20462, 1)   # kg → lbs
    if metric == "waist":
        return round(stored_value / 2.54, 1)       # cm → in
    return stored_value  # mmHg, bpm, % — no conversion needed


def _fmt_value(value: float, metric: str) -> str:
    """Format a display value as a string."""
    if metric in ("bp_systolic", "bp_diastolic", "heart_rate"):
        return str(int(round(value)))
    return f"{value:.1f}"
