"""Data manager utilities: JSON persistence, defaults, and environment loading.

Goals:
- Keep I/O simple and reliable (atomic writes).
- Make defaults coherent and reusable.
- Be resilient to missing/partial/corrupted JSON (backup corrupted files).
- Avoid storing stale derived values (e.g., age) while remaining backward compatible.

This module is intentionally dependency-light and safe to port across projects.
"""

from __future__ import annotations

import orjson

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

try:
    from core.console_manager import cprint  # type: ignore
except Exception:  # pragma: no cover
    def cprint(msg: str) -> None:  # type: ignore
        print(msg)


# ----------------------------
# Paths
# ----------------------------
 
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

PROFILE_PATH = DATA_DIR / "profile.json"
CONFIG_PATH = DATA_DIR / "config.json"
GOALS_PATH = DATA_DIR / "goals.json"
CUSTOM_FOODS_PATH = DATA_DIR / "custom_foods.json"
CUSTOM_RECIPES_PATH = DATA_DIR / "custom_recipes.json" 
CUSTOM_MEALS_PATH = DATA_DIR / "custom_meals.json"  

# ----------------------------
# Time helpers
# ----------------------------
def iso_now() -> str:
    """ISO 8601 timestamp with local timezone offset (seconds precision)."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

# ----------------------------
# Defaults (generated, not frozen at import time)
# ----------------------------
def default_profile() -> Dict[str, Any]:
    """Default profile schema.

    Note: we do not store derived/stale values like 'age' as source-of-truth.
    """
    return {
        "name": "",
        "sex_for_bmr": "",
        "birthdate": "",  # YYYY-MM-DD
        "age": "",  # legacy / optional; prefer computing from birthdate
        "height_cm": "",
        "weight_kg": "",
        "activity_level": "",
    }


def default_goals() -> Dict[str, Any]:
    return {
        "goal_type": None,  # "lose", "maintain", "gain"
        "weekly_rate": None,
        "target_weight": None,
        "start_weight": None,
    
        "created_at": iso_now(),
        "updated_at": iso_now(),
    }


def default_config() -> Dict[str, Any]:
    return {
        # app metadata
        "schema_version": 1, 
        "setup_completed": False,
       
        # preferences 
        "units": "imperial",
        "calorie_target_mode": "auto", # "auto" or "manual" 
        "manual_calorie_target": None, # null if calorie_target_mode isn't manual
    }


def default_custom_foods() -> Dict[str, Any]:
    return {"foods": []}


# Map file paths to their default factories
_DEFAULTS: Dict[Path, Callable[[], Dict[str, Any]]] = {
    PROFILE_PATH: default_profile,
    GOALS_PATH: default_goals,
    CONFIG_PATH: default_config,
    CUSTOM_FOODS_PATH: default_custom_foods,
}

    


# ----------------------------
# JSON I/O
# ----------------------------
def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    """Atomically save JSON data to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as f:
        f.write(orjson.dumps(data, option=orjson.OPT_INDENT_2)) 
    os.replace(tmp, path)


def _backup_corrupt_file(path: Path) -> Optional[Path]:
    """Rename a corrupt JSON file so the user can recover it later."""
    if not path.exists():
        return None
    backup = path.with_name(f"{path.stem}.corrupt-{datetime.now().strftime('%Y%m%d-%H%M%S')}{path.suffix}")
    try:
        os.replace(path, backup)
        return backup
    except OSError:
        # If rename fails (permissions, weird FS), we don't hard fail.
        return None


def _merge_defaults(data: Any, defaults: Dict[str, Any]) -> Dict[str, Any]:
    """Merge defaults into loaded data without dropping user keys."""
    if not isinstance(data, dict):
        return defaults.copy()
    merged = defaults.copy()
    merged.update(data)
    return merged


def save_json(path: Path, data: Dict[str, Any]) -> None:
    """Public save function (kept for compatibility)."""
    _atomic_write_json(path, data)


def load_json(path: Path) -> Dict[str, Any]:
    """Load JSON, repairing missing/partial/corrupt files.

    Behavior:
    - If file missing -> create with defaults and return defaults.
    - If corrupt -> back it up, recreate defaults, return defaults.
    - If valid but missing keys -> merge defaults, write back, return merged.
    """
    default_factory = _DEFAULTS.get(path)
    if default_factory is None:
        raise RuntimeError(f"Unknown JSON path (no defaults registered): {path}")

    defaults = default_factory()

    if not path.exists():
        _atomic_write_json(path, defaults)
        return defaults

    try:
        with path.open("rb") as f:
            loaded = orjson.loads(f.read())
    except json.JSONDecodeError:
        backup = _backup_corrupt_file(path)
        if backup:
            cprint(f"[warning] {path.name} was corrupted. Backed up to {backup.name} and rebuilt defaults.")
        else:
            cprint(f"[warning] {path.name} was corrupted. Rebuilt defaults.")
        _atomic_write_json(path, defaults)
        return defaults

    merged = _merge_defaults(loaded, defaults)

    # Normalize/validate a couple of high-value fields without being strict.
    units = (merged.get("units") or "").strip().lower()
    if path == CONFIG_PATH:
        if units not in {"imperial", "metric"}:
            merged["units"] = defaults["units"]

    # Write back if we repaired/normalized anything.
    if merged != loaded:
        _atomic_write_json(path, merged)

    return merged


def init_files() -> None:
    """Ensure data directory and JSON files exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for p, factory in _DEFAULTS.items():
        if not p.exists():
            _atomic_write_json(p, factory())


# ----------------------------
# Parsing helpers (port-friendly)
# ----------------------------
def _parse_birthdate(birthdate_str: str):
    """Return datetime.date or None."""
    s = (birthdate_str or "").strip()
    if not s:
        return None
    try:
        dt = datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None
    if dt > datetime.now().date():
        return None
    return dt


def _compute_age_years(birthdate_date) -> int:
    today = datetime.now().date()
    years = today.year - birthdate_date.year
    if (today.month, today.day) < (birthdate_date.month, birthdate_date.day):
        years -= 1
    return max(years, 0)


def _parse_positive_number(s: str) -> Optional[float]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return v if v > 0 else None


# ----------------------------
# Environment
# ----------------------------
@dataclass
class Environment:
    config: Dict[str, Any]
    profile: Dict[str, Any]
    goals: Dict[str, Any]
    
    def reload(self) -> None: 
        """Re-read all data files from disk into this environment instance.""" 
        self.config = load_json(CONFIG_PATH) 
        self.profile = load_json(PROFILE_PATH) 
        self.goals = load_json(GOALS_PATH) 


def ensure_environment() -> Environment:
    """Create/load all JSON files and return an in-memory environment bundle."""
    init_files()
    return Environment(
        config=load_json(CONFIG_PATH),
        profile=load_json(PROFILE_PATH),
        goals=load_json(GOALS_PATH),
    )