"""fdc_importer.py — Build a local SQLite database from USDA FoodData Central JSON files.

Supported datasets (JSON format):
    - Foundation Foods  (FoodData_Central_foundation_food_json_*.zip / *.json)
    - SR Legacy         (FoodData_Central_sr_legacy_food_json_*.zip  / *.json)
    - Branded Foods     (FoodData_Central_branded_food_json_*.zip    / *.json)

Usage (called from the settings menu):
    from core.fdc_importer import build_database
    build_database(json_paths=[...], db_path=..., progress_cb=print)

All nutrients are stored per 100 g. Branded Foods are already normalised to
per-100 g by USDA before distribution, so no conversion is needed.

Deduplication:
    Foundation preferred over SR Legacy when ndbNumber matches.
    Branded Foods have their own FDC IDs; no overlap with the other two.
"""

from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Nutrient IDs we care about (USDA internal IDs, stable across all datasets)
# ---------------------------------------------------------------------------
_KCAL    = 1008
_PROTEIN = 1003
_CARBS   = 1005
_FAT     = 1004

_TARGET_NUTRIENTS = {_KCAL, _PROTEIN, _CARBS, _FAT}

# ---------------------------------------------------------------------------
# Dataset identification
# ---------------------------------------------------------------------------
_DATASET_KEYS = {
    "FoundationFoods": "foundation",
    "SRLegacyFoods":   "sr_legacy",
    "BrandedFoods":    "branded",
}


def _sniff_dataset(data: dict) -> Tuple[str, str]:
    """Return (list_key, source_label) for a loaded JSON dict."""
    for key, label in _DATASET_KEYS.items():
        if key in data:
            return key, label
    raise ValueError(f"Unrecognised dataset. Top-level keys: {list(data.keys())}")


# ---------------------------------------------------------------------------
# JSON loading (handles raw .json or .zip containing one .json)
# ---------------------------------------------------------------------------
def _load_json(path: Path) -> dict:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            json_names = [n for n in zf.namelist() if n.endswith(".json")]
            if not json_names:
                raise ValueError(f"No .json file found inside {path.name}")
            with zf.open(json_names[0]) as f:
                return json.load(f)
    else:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)


# ---------------------------------------------------------------------------
# Per-dataset record extractors
# ---------------------------------------------------------------------------
def _get_macros(food: dict) -> Dict[int, Optional[float]]:
    result: Dict[int, Optional[float]] = {}
    for n in food.get("foodNutrients", []):
        nid = n.get("nutrient", {}).get("id")
        if nid in _TARGET_NUTRIENTS:
            result[nid] = n.get("amount")
    return result


def _best_portion(food: dict) -> Tuple[Optional[str], Optional[float]]:
    """Return (label, grams) for the most useful portion, or (None, None)."""
    portions = food.get("foodPortions", [])
    if not portions:
        return None, None
    # Prefer portions whose unit is not 'undetermined'
    good = [p for p in portions if p.get("measureUnit", {}).get("name", "undetermined") != "undetermined"]
    chosen = good[0] if good else portions[0]

    unit      = chosen.get("measureUnit", {})
    unit_name = unit.get("name", "")
    if unit_name.lower() == "undetermined":
        unit_name = ""
    modifier  = chosen.get("modifier", "")
    amount    = chosen.get("amount", 1)
    grams     = chosen.get("gramWeight")

    parts = [str(amount), unit_name, modifier]
    label = " ".join(p for p in parts if p).strip()
    return label or None, grams


def _extract_foundation_sr(food: dict, source: str,
                            sr_by_ndb: Dict[int, dict]) -> Optional[dict]:
    """Extract a normalised record from a Foundation or SR Legacy food entry."""
    macros = _get_macros(food)

    # Foundation foods sometimes lack kcal/macros; fall back to SR by NDB number
    if source == "foundation" and not all(k in macros for k in _TARGET_NUTRIENTS):
        ndb = food.get("ndbNumber")
        if ndb and ndb in sr_by_ndb:
            sr_macros = _get_macros(sr_by_ndb[ndb])
            for k in _TARGET_NUTRIENTS:
                if k not in macros and k in sr_macros:
                    macros[k] = sr_macros[k]

    kcal = macros.get(_KCAL)
    if kcal is None:
        return None  # skip foods with no calorie data at all

    label, grams = _best_portion(food)
    category = food.get("foodCategory", {})
    category_str = category.get("description") if isinstance(category, dict) else None

    return {
        "fdc_id":           food["fdcId"],
        "description":      food["description"].strip(),
        "source":           source,
        "category":         category_str,
        "brand_owner":      None,
        "kcal_per_100g":    kcal,
        "protein_per_100g": macros.get(_PROTEIN),
        "carbs_per_100g":   macros.get(_CARBS),
        "fat_per_100g":     macros.get(_FAT),
        "serving_label":    label,
        "serving_grams":    grams,
    }


def _extract_branded(food: dict) -> Optional[dict]:
    """Extract a normalised record from a Branded Foods entry.

    USDA already normalises branded nutrients to per-100 g, so no conversion
    is needed. The serving info comes from servingSize / householdServingFullText.
    """
    macros = _get_macros(food)
    kcal = macros.get(_KCAL)
    if kcal is None:
        return None

    # Serving label: prefer human-readable household description
    household = (food.get("householdServingFullText") or "").strip()
    serving_size = food.get("servingSize")        # numeric, in servingSizeUnit
    serving_unit = (food.get("servingSizeUnit") or "g").strip()

    if household:
        serving_label = household
    elif serving_size is not None:
        serving_label = f"{serving_size} {serving_unit}".strip()
    else:
        serving_label = None

    # serving_grams: servingSize is in servingSizeUnit; usually "g" for branded
    try:
        serving_grams = float(serving_size) if serving_size is not None else None
        if serving_unit.lower() not in ("g", "grams", "gram"):
            serving_grams = None  # don't guess non-gram units
    except (TypeError, ValueError):
        serving_grams = None

    description = (food.get("description") or "").strip()
    if not description:
        return None

    category = (food.get("brandedFoodCategory") or "").strip() or None
    brand    = (food.get("brandOwner") or "").strip() or None

    return {
        "fdc_id":           food["fdcId"],
        "description":      description,
        "source":           "branded",
        "category":         category,
        "brand_owner":      brand,
        "kcal_per_100g":    kcal,
        "protein_per_100g": macros.get(_PROTEIN),
        "carbs_per_100g":   macros.get(_CARBS),
        "fat_per_100g":     macros.get(_FAT),
        "serving_label":    serving_label,
        "serving_grams":    serving_grams,
    }


# ---------------------------------------------------------------------------
# Iterator that yields normalised records from a list of source files
# ---------------------------------------------------------------------------
def _iter_records(
    json_paths: List[Path],
    progress_cb: Callable[[str], None],
) -> Iterator[dict]:
    """Yield normalised food dicts from all provided JSON/ZIP paths.

    Processes Foundation and SR Legacy first so we can build the NDB overlap
    set before streaming Branded (which is huge).
    """
    foundation_foods: List[dict] = []
    sr_foods: List[dict] = []
    branded_paths: List[Path] = []

    # ---- Sort paths by dataset type ----
    for path in json_paths:
        progress_cb(f"Reading {path.name}…")
        data = _load_json(path)
        list_key, source = _sniff_dataset(data)
        foods = data[list_key]

        if source == "foundation":
            foundation_foods = foods
        elif source == "sr_legacy":
            sr_foods = foods
        elif source == "branded":
            branded_paths.append(path)  # re-load later to stream

    # ---- Build SR lookup by NDB number (for Foundation fallback) ----
    sr_by_ndb: Dict[int, dict] = {
        f["ndbNumber"]: f for f in sr_foods if f.get("ndbNumber")
    }

    # ---- Foundation: preferred over SR for overlapping NDB numbers ----
    fn_ndb_set: set = set()
    progress_cb(f"Importing Foundation Foods ({len(foundation_foods)} entries)…")
    for food in foundation_foods:
        rec = _extract_foundation_sr(food, "foundation", sr_by_ndb)
        if rec:
            fn_ndb_set.add(food.get("ndbNumber"))
            yield rec

    # ---- SR Legacy: skip any NDB that Foundation already covered ----
    progress_cb(f"Importing SR Legacy ({len(sr_foods)} entries)…")
    skipped = 0
    for food in sr_foods:
        ndb = food.get("ndbNumber")
        if ndb and ndb in fn_ndb_set:
            skipped += 1
            continue
        rec = _extract_foundation_sr(food, "sr_legacy", sr_by_ndb)
        if rec:
            yield rec
    if skipped:
        progress_cb(f"  Skipped {skipped} SR Legacy entries superseded by Foundation Foods.")

    # ---- Branded: stream from each branded path ----
    for path in branded_paths:
        progress_cb(f"Importing Branded Foods from {path.name}…")
        progress_cb("  (This may take several minutes for large files…)")
        data = _load_json(path)
        list_key, _ = _sniff_dataset(data)
        foods = data[list_key]
        progress_cb(f"  {len(foods):,} branded entries found.")
        count = 0
        for food in foods:
            rec = _extract_branded(food)
            if rec:
                count += 1
                yield rec
                if count % 50_000 == 0:
                    progress_cb(f"  …{count:,} branded foods processed…")
        progress_cb(f"  Branded import complete: {count:,} foods imported.")


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_DDL = """
CREATE TABLE IF NOT EXISTS foods (
    fdc_id            INTEGER PRIMARY KEY,
    description       TEXT    NOT NULL,
    source            TEXT    NOT NULL,
    category          TEXT,
    brand_owner       TEXT,
    kcal_per_100g     REAL,
    protein_per_100g  REAL,
    carbs_per_100g    REAL,
    fat_per_100g      REAL,
    serving_label     TEXT,
    serving_grams     REAL
);

CREATE VIRTUAL TABLE IF NOT EXISTS foods_fts USING fts5(
    description,
    brand_owner,
    category,
    content=foods,
    content_rowid=fdc_id,
    tokenize='unicode61 remove_diacritics 2'
);
"""

_INSERT_FOOD = """
INSERT OR REPLACE INTO foods (
    fdc_id, description, source, category, brand_owner,
    kcal_per_100g, protein_per_100g, carbs_per_100g, fat_per_100g,
    serving_label, serving_grams
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_INSERT_FTS = """
INSERT INTO foods_fts (rowid, description, brand_owner, category)
VALUES (?, ?, ?, ?)
"""

_BATCH_SIZE = 2_000


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def build_database(
    json_paths: List[Path],
    db_path: Path,
    progress_cb: Callable[[str], None] = print,
) -> int:
    """Import JSON datasets into a SQLite FTS database.

    Args:
        json_paths:  List of .json or .zip file paths (Foundation, SR, Branded).
        db_path:     Where to write the SQLite file (created or replaced).
        progress_cb: Called with status strings throughout the import.

    Returns:
        Total number of food records written.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove any existing database so we start clean
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_DDL)
        conn.commit()

        food_batch:  List[Tuple] = []
        fts_batch:   List[Tuple] = []
        total = 0

        def _flush():
            nonlocal total
            conn.executemany(_INSERT_FOOD, food_batch)
            conn.executemany(_INSERT_FTS,  fts_batch)
            conn.commit()
            total += len(food_batch)
            food_batch.clear()
            fts_batch.clear()

        for rec in _iter_records(json_paths, progress_cb):
            food_batch.append((
                rec["fdc_id"],
                rec["description"],
                rec["source"],
                rec["category"],
                rec["brand_owner"],
                rec["kcal_per_100g"],
                rec["protein_per_100g"],
                rec["carbs_per_100g"],
                rec["fat_per_100g"],
                rec["serving_label"],
                rec["serving_grams"],
            ))
            fts_batch.append((
                rec["fdc_id"],
                rec["description"],
                rec["brand_owner"],
                rec["category"],
            ))

            if len(food_batch) >= _BATCH_SIZE:
                _flush()
                if total % 100_000 == 0 and total > 0:
                    progress_cb(f"  {total:,} total records written…")

        if food_batch:
            _flush()

        # Optimise for read performance
        progress_cb("Optimising database…")
        conn.execute("INSERT INTO foods_fts(foods_fts) VALUES('optimize')")
        conn.execute("ANALYZE")
        conn.commit()

        progress_cb(f"Done. {total:,} foods imported to {db_path}.")
        return total

    except Exception:
        conn.close()
        if db_path.exists():
            db_path.unlink()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Search (used by menu_food_diary at log time)
# ---------------------------------------------------------------------------
def search_foods(
    db_path: Path,
    query: str,
    limit: int = 20,
    source_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Full-text search the database. Returns a list of food dicts.

    Args:
        query:         User's search string (e.g. 'chicken breast').
        limit:         Max results to return.
        source_filter: Optional 'foundation', 'sr_legacy', or 'branded'.
    """
    if not db_path.exists():
        return []

    # Build an FTS5 prefix query: each word gets a * suffix for partial matching
    terms = query.strip().split()
    if not terms:
        return []
    fts_query = " ".join(t + "*" for t in terms)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if source_filter:
            sql = """
                SELECT f.*
                FROM foods f
                JOIN foods_fts fts ON fts.rowid = f.fdc_id
                WHERE foods_fts MATCH ?
                  AND f.source = ?
                ORDER BY rank
                LIMIT ?
            """
            rows = conn.execute(sql, (fts_query, source_filter, limit)).fetchall()
        else:
            sql = """
                SELECT f.*
                FROM foods f
                JOIN foods_fts fts ON fts.rowid = f.fdc_id
                WHERE foods_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """
            rows = conn.execute(sql, (fts_query, limit)).fetchall()

        return [dict(r) for r in rows]
    finally:
        conn.close()


def db_stats(db_path: Path) -> Optional[Dict[str, Any]]:
    """Return record counts by source, or None if the DB doesn't exist."""
    if not db_path.exists():
        return None
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT source, COUNT(*) FROM foods GROUP BY source"
        ).fetchall()
        counts = {row[0]: row[1] for row in rows}
        counts["total"] = sum(counts.values())
        return counts
    finally:
        conn.close()
