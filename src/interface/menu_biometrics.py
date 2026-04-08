from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from rich.table import Table
from rich.text import Text

from interface.prompts import _prompt_str, _prompt_float, _prompt_choice
from interface.common import MenuItem, build_menu_panel, run_menu_action

from core.console_manager import cprint, cinput, clear_console, get_console
from core.data_manager import (
    Environment,
    DATA_DIR,
    _atomic_write_json,
)
from core.log_manager import append_entry, delete_entry, load_day


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BIOMETRICS_PATH = DATA_DIR / "biometrics.json"

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

# Metrics displayed as a pair (rendered on one row).
_BP_PAIR = ("bp_systolic", "bp_diastolic")

# Row style hint per metric for the log table.
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
    """Return all biometric entries logged on *d*, sorted by logged_at."""
    ds = d.isoformat()
    entries = _load_biometrics().get("entries", [])
    return [e for e in entries if e.get("date") == ds]


def _make_entry(
    metric: str,
    value: float,
    d: date,
    note: str = "",
) -> Dict[str, Any]:
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
    data  = _load_biometrics()
    before = len(data["entries"])
    data["entries"] = [e for e in data["entries"] if e.get("id") != entry_id]
    if len(data["entries"]) < before:
        _save_biometrics(data)
        return True
    return False


# ---------------------------------------------------------------------------
# Profile weight sync
# ---------------------------------------------------------------------------

def _sync_weight_to_profile(env: Environment, weight_kg: float) -> None:
    """Write *weight_kg* (canonical metric unit) back to the user's profile."""
    try:
        profile_path = DATA_DIR / "profile.json"
        if profile_path.exists():
            with profile_path.open("r", encoding="utf-8") as f:
                profile = json.load(f)
        else:
            profile = {}
        
        profile.pop("weight_lbs", None)
        profile["weight_kg"] = round(weight_kg, 2)
        _atomic_write_json(profile_path, profile)
    except (OSError, json.JSONDecodeError):
        pass  # Non-fatal — biometric entry is still saved.


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_biometrics_menu(env: Environment) -> None:
    units       = str(env.config.get("units", "imperial")).strip().lower()
    viewed_date = date.today()

    while True:
        clear_console()
        today    = date.today()
        is_today = viewed_date == today

        _render_biometrics_log(viewed_date, units)
        _render_biometrics_nav(is_today)

        items = [
            MenuItem("1", "Log a biometric",   lambda _: _log_biometric(viewed_date, units, env)),
            MenuItem("2", "Delete an entry",    lambda _: _delete_biometric(viewed_date, units),
                     enabled=bool(_entries_for_date(viewed_date))),
            MenuItem("b", "Back", lambda _: None),
        ]

        cprint("")
        cprint(build_menu_panel("Biometrics", items, note="Select an option."))

        choice = cinput("\n[bold magenta]Choice[/bold magenta]: ").strip().lower()

        match choice:
            case "<":
                viewed_date -= timedelta(days=1)
                continue
            case ">":
                if viewed_date < today:
                    viewed_date += timedelta(days=1)
                continue
            case "t":
                viewed_date = today
                continue
            case "g":
                jumped = _prompt_date(today)
                if jumped is not None:
                    viewed_date = jumped
                continue
            case "b":
                return

        if not run_menu_action(items, choice, env):
            cprint("[yellow]Invalid choice. Press Enter to try again.[/yellow]")
            cinput("")


# ---------------------------------------------------------------------------
# Date navigation
# ---------------------------------------------------------------------------

def _prompt_date(today: date) -> Optional[date]:
    """Accept YYYY-MM-DD, MM-DD, or MM/DD. Reject future dates."""
    cprint("\n[dim]Enter a date — formats: YYYY-MM-DD, MM-DD, or MM/DD (blank to cancel)[/dim]")
    raw = cinput("Date: ").strip()
    if not raw:
        return None

    normalized = raw.replace("/", "-")
    parsed: Optional[date] = None
    for fmt in ("%Y-%m-%d", "%m-%d"):
        try:
            candidate = normalized if fmt != "%m-%d" else f"{today.year}-{normalized}"
            parsed = date.fromisoformat(candidate)
            break
        except ValueError:
            continue

    if parsed is None:
        cprint("[yellow]Couldn't parse that date. Try YYYY-MM-DD or MM-DD.[/yellow]")
        cinput("Press Enter to continue.")
        return None
    if parsed > today:
        cprint("[yellow]Can't navigate to a future date.[/yellow]")
        cinput("Press Enter to continue.")
        return None
    return parsed


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def _date_label(d: date, today: date) -> str:
    delta = (today - d).days
    if delta == 0:
        return f"{d.strftime('%A, %B')} {d.day} [green]· today[/green]"
    if delta == 1:
        return f"{d.strftime('%A, %B')} {d.day} [yellow]· yesterday[/yellow]"
    return f"{d.strftime('%A, %B')} {d.day} [yellow]· {delta} days ago[/yellow]"


def _render_biometrics_log(d: date, units: str) -> None:
    console  = get_console()
    entries  = _entries_for_date(d)
    today    = date.today()

    table = Table(
        title=f"[bold]Biometrics Log[/bold]  [dim]{_date_label(d, today)}[/dim]",
        show_lines=False,
        show_header=True,
        header_style="bold",
        title_justify="left",
    )
    table.add_column("ID",     style="dim", width=10, no_wrap=True)
    table.add_column("Metric", min_width=18)
    table.add_column("Value",  justify="right", width=12, no_wrap=True)
    table.add_column("Note",   min_width=16, max_width=30)

    if not entries:
        table.add_row("[dim]—[/dim]", "[dim]Nothing logged yet[/dim]", "", "")
    else:
        # Render BP as a single "120 / 80" row when both halves are present.
        rendered_ids: set = set()
        for e in entries:
            if e["id"] in rendered_ids:
                continue

            metric = e["metric"]
            style  = _METRIC_STYLE.get(metric, "white")

            if metric == "bp_systolic":
                # Look for a matching diastolic entry logged on same date.
                dia = next(
                    (x for x in entries if x["metric"] == "bp_diastolic"
                     and x["id"] not in rendered_ids),
                    None,
                )
                if dia:
                    rendered_ids.add(e["id"])
                    rendered_ids.add(dia["id"])
                    bp_str = f"{int(e['value'])} / {int(dia['value'])} mmHg"  # mmHg: no conversion needed
                    note   = e.get("note") or dia.get("note") or ""
                    table.add_row(
                        f"{e['id']}, {dia['id']}",
                        Text("Blood Pressure", style=style),
                        bp_str,
                        note,
                    )
                    continue

            if metric == "bp_diastolic" and e["id"] in rendered_ids:
                continue

            rendered_ids.add(e["id"])
            label, unit = _metric_label_unit(metric, units)
            display_val = _to_display(e["value"], metric, units)
            val_str     = f"{_fmt_value(display_val, metric)} {unit}"
            table.add_row(
                e["id"],
                Text(label, style=style),
                val_str,
                e.get("note", ""),
            )

    console.print(table)


def _render_biometrics_nav(is_today: bool) -> None:
    nav = Text()
    nav.append("  ")

    nav.append("[", "bright_black")
    nav.append("<", "bold cyan")
    nav.append("]", "bright_black")
    nav.append(" Prev day", "white")
    nav.append("   ")

    nav.append("[", "bright_black")
    nav.append(">", "bold cyan" if not is_today else "dim")
    nav.append("]", "bright_black")
    nav.append(" Next day", "white" if not is_today else "dim")
    nav.append("   ")

    nav.append("[", "bright_black")
    nav.append("g", "bold cyan")
    nav.append("]", "bright_black")
    nav.append(" Go to date", "white")

    if not is_today:
        nav.append("   ")
        nav.append("[", "bright_black")
        nav.append("t", "bold cyan")
        nav.append("]", "bright_black")
        nav.append(" Today", "white")

    cprint("")
    cprint(nav)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _log_biometric(d: date, units: str, env: Environment) -> None:
    clear_console()
    cprint("[bold]Log Biometric[/bold]\n")

    # Present metric choices, skipping the raw bp_diastolic (it's prompted
    # alongside systolic as a pair).
    choices = [
        ("1", "Weight"),
        ("2", "Blood Pressure"),
        ("3", "Heart Rate"),
        ("4", "Waist"),
        ("5", "Body Fat %"),
        ("b", "Cancel"),
    ]
    for key, label in choices:
        if key == "b":
            cprint(f"  [dim](b)[/dim] {label}")
        else:
            cprint(f"  [cyan]{key}[/cyan]) {label}")

    cprint("")
    pick = cinput("Metric: ").strip().lower()

    if pick == "b" or not pick:
        return
    elif pick == "1":
        _log_weight(d, units, env)
    elif pick == "2":
        _log_blood_pressure(d)
    elif pick == "3":
        _log_simple(d, "heart_rate", "Heart Rate", "bpm", min_=20.0)
    elif pick == "4":
        _log_waist(d, units)
    elif pick == "5":
        _log_simple(d, "body_fat_pct", "Body Fat %", "%", min_=1.0)
    else:
        cprint("[yellow]Invalid choice.[/yellow]")
        cinput("\nPress Enter to continue.")


def _log_weight(d: date, units: str, env: Environment) -> None:
    """Prompt for weight and optionally sync to profile if d == today.
    Always stores in kg (canonical metric unit)."""
    if units == "imperial":
        val_lbs = _prompt_float("Weight (lbs): ", min_=1.0)
        if val_lbs is None:
            return
        weight_kg    = round(val_lbs / 2.20462, 2)
        display_val  = round(val_lbs, 1)
        display_unit = "lbs"
    else:
        weight_kg = _prompt_float("Weight (kg): ", min_=1.0)
        if weight_kg is None:
            return
        weight_kg    = round(weight_kg, 2)
        display_val  = weight_kg
        display_unit = "kg"

    note  = cinput("Note (optional): ").strip()
    entry = _make_entry("weight", weight_kg, d, note)
    _append_biometric_entry(entry)

    cprint(f"[green]✔ Logged weight: {display_val} {display_unit}[/green]")

    if d == date.today():
        _sync_weight_to_profile(env, weight_kg)
        cprint("[dim]  (profile weight updated)[/dim]")

    cinput("\nPress Enter to continue.")


def _log_blood_pressure(d: date) -> None:
    """Prompt for systolic + diastolic and save as two linked entries."""
    cprint("\n[dim]Blood pressure is stored as systolic / diastolic (mmHg).[/dim]\n")
    systolic = _prompt_float("Systolic (upper number): ", min_=50.0)
    if systolic is None:
        return
    diastolic = _prompt_float("Diastolic (lower number): ", min_=20.0)
    if diastolic is None:
        return
    note = cinput("Note (optional): ").strip()

    _append_biometric_entry(_make_entry("bp_systolic",  systolic,  d, note))
    _append_biometric_entry(_make_entry("bp_diastolic", diastolic, d, ""))

    cprint(
        f"[green]✔ Logged BP: {int(systolic)} / {int(diastolic)} mmHg[/green]"
    )
    _bp_category_hint(systolic, diastolic)
    cinput("\nPress Enter to continue.")


def _log_waist(d: date, units: str) -> None:
    """Prompt for waist in the user's preferred unit; always store in cm."""
    if units == "imperial":
        val_in = _prompt_float("Waist (in): ", min_=10.0)
        if val_in is None:
            return
        waist_cm     = round(val_in * 2.54, 2)
        display_val  = round(val_in, 1)
        display_unit = "in"
    else:
        waist_cm = _prompt_float("Waist (cm): ", min_=25.0)
        if waist_cm is None:
            return
        waist_cm     = round(waist_cm, 2)
        display_val  = waist_cm
        display_unit = "cm"

    note  = cinput("Note (optional): ").strip()
    entry = _make_entry("waist", waist_cm, d, note)
    _append_biometric_entry(entry)
    cprint(f"[green]✔ Logged waist: {display_val} {display_unit}[/green]")
    cinput("\nPress Enter to continue.")


def _log_simple(
    d: date,
    metric: str,
    label: str,
    unit: str,
    min_: float = 0.0,
) -> None:
    val = _prompt_float(f"{label} ({unit}): ", min_=min_)
    if val is None:
        return
    note  = cinput("Note (optional): ").strip()
    entry = _make_entry(metric, val, d, note)
    _append_biometric_entry(entry)
    cprint(f"[green]✔ Logged {label}: {_fmt_value(val, metric)} {unit}[/green]")
    cinput("\nPress Enter to continue.")


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------

# TODO: Make it so that, if you delete the most recent logged weight, the user's current weight reverts to the newest remaining weight (or to the starting weight if no logged weights exist)
def _delete_biometric(d: date, units: str) -> None:
    clear_console()
    entries = _entries_for_date(d)

    if not entries:
        cprint("[yellow]No entries to delete.[/yellow]")
        cinput("\nPress Enter to continue.")
        return

    cprint("[bold]Delete Entry[/bold]\n")

    for e in entries:
        metric = e["metric"]
        style  = _METRIC_STYLE.get(metric, "white")
        label, unit = _metric_label_unit(metric, units)
        display_val = _to_display(e["value"], metric, units)
        val_str = f"{_fmt_value(display_val, metric)} {unit}"
        cprint(
            f"  [cyan]{e['id']}[/cyan]  "
            f"[{style}]{label}[/{style}]  "
            f"{val_str}"
            + (f"  [dim]{e['note']}[/dim]" if e.get("note") else "")
        )

    import re
    raw = cinput("\nEnter ID(s) to delete — separate multiple with ',' or ';' (or blank to cancel): ").strip()
    if not raw:
        return

    ids_to_delete = [x.strip() for x in re.split(r"[,;]", raw) if x.strip()]
    deleted, not_found = 0, []
    for entry_id in ids_to_delete:
        if _delete_biometric_entry(entry_id):
            deleted += 1
        else:
            not_found.append(entry_id)

    if deleted:
        cprint(f"[green]✔ {deleted} entr{'y' if deleted == 1 else 'ies'} deleted.[/green]")
    if not_found:
        cprint(f"[yellow]No entry found for ID(s): {', '.join(not_found)}[/yellow]")

    cinput("\nPress Enter to continue.")


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

def _metric_label_unit(metric: str, units: str) -> tuple[str, str]:
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
    """Format a stored value for display."""
    if metric in ("bp_systolic", "bp_diastolic", "heart_rate"):
        return str(int(round(value)))
    return f"{value:.1f}"


def _bp_category_hint(systolic: float, diastolic: float) -> None:
    """Print an informational BP category label (AHA guidelines)."""
    s, d = systolic, diastolic
    if s < 120 and d < 80:
        cat, style = "Normal",                  "green"
    elif s < 130 and d < 80:
        cat, style = "Elevated",                "yellow"
    elif s < 140 or d < 90:
        cat, style = "High — Stage 1",          "yellow"
    elif s >= 180 or d >= 120:
        cat, style = "Hypertensive Crisis",     "bold red"
    else:
        cat, style = "High — Stage 2",          "red"
    cprint(f"  [{style}]Category: {cat}[/{style}]  [dim](AHA guidelines)[/dim]")
