"""
menu_biometrics_trends.py
─────────────────────────
Biometric trend viewer powered by Plotly.

Entry point: run_trends_menu(env)

Design decisions
────────────────
* Launched as "View Trends" from the biometrics menu (nested option, not a
  top-of-menu dashboard) so the log stays the primary view.
* Fully customizable: any combination of metrics can be overlaid on one chart.
* BP systolic + diastolic are always bundled together as one "Blood Pressure"
  toggle (they share a y-axis and make no sense alone).
* Weight and waist use a *secondary* y-axis when overlaid with mmHg / bpm
  metrics, preventing scale crush.
* Date-range presets: 7 d / 30 d / 90 d / all-time, plus a custom range.
* Output: opens an HTML file in the system browser via plotly.io.show(),
  which works cross-platform with no display server required from the CLI.
"""

from __future__ import annotations

import json
import webbrowser
import tempfile
import os
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.console_manager import cprint, cinput, clear_console
from core.data_manager import Environment, DATA_DIR

from interface.shared import MenuItem, build_menu_panel, run_menu_action
from interface.biometrics_core import (
    _load_biometrics,
    _to_display,
    _METRIC_DEFS,
    _METRIC_STYLE,
)

# ─────────────────────────────────────────────────────────────────────────────
# Metric catalogue
# ─────────────────────────────────────────────────────────────────────────────

# Each entry: key → (display_label, plotly_color, y_axis_group)
# y_axis_group:
#   "weight_like"  → kg / lbs / cm / in  (secondary y-axis when mixed)
#   "pressure"     → mmHg
#   "rate"         → bpm
#   "percent"      → %
_TREND_META: Dict[str, Tuple[str, str, str]] = {
    "weight":       ("Weight",          "#17becf", "weight_like"),
    "bp_systolic":  ("Systolic BP",     "#d62728", "pressure"),
    "bp_diastolic": ("Diastolic BP",    "#ff7f7e", "pressure"),
    "heart_rate":   ("Heart Rate",      "#9467bd", "rate"),
    "waist":        ("Waist",           "#e6a817", "weight_like"),
    "body_fat_pct": ("Body Fat %",      "#2ca02c", "percent"),
}

# Grouped toggle: selecting "bp" enables both systolic + diastolic.
_BP_GROUP = {"bp_systolic", "bp_diastolic"}

# Human-readable toggle choices (what the user sees in the menu)
_TOGGLE_CHOICES = [
    ("w",  "Weight"),
    ("bp", "Blood Pressure  (systolic + diastolic)"),
    ("hr", "Heart Rate"),
    ("wt", "Waist"),
    ("bf", "Body Fat %"),
]

_TOGGLE_KEY_TO_METRICS: Dict[str, List[str]] = {
    "w":  ["weight"],
    "bp": ["bp_systolic", "bp_diastolic"],
    "hr": ["heart_rate"],
    "wt": ["waist"],
    "bf": ["body_fat_pct"],
}

# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_trends_menu(env: Environment) -> None:
    """Top-level trends menu: configure and render charts."""
    units = str(env.config.get("units", "imperial")).strip().lower()

    # Default state
    enabled: set[str] = {"weight"}          # metric keys currently toggled ON
    range_days: Optional[int] = 30          # None = all-time
    custom_start: Optional[date] = None
    custom_end:   Optional[date] = None

    while True:
        clear_console()
        _render_trends_header(enabled, range_days, custom_start, custom_end, units)

        items = [
            MenuItem("1", "Toggle metrics",    lambda _: None),   # handled below
            MenuItem("2", "Change date range", lambda _: None),
            MenuItem("3", "View chart",        lambda _: None),
            MenuItem("b", "Back",              lambda _: None),
        ]

        cprint("")
        cprint(build_menu_panel("Biometric Trends", items, note="Select an option."))
        choice = cinput("\n[bold magenta]Choice[/bold magenta]: ").strip().lower()

        if choice == "b":
            return
        elif choice == "1":
            enabled = _toggle_metrics_menu(enabled)
        elif choice == "2":
            range_days, custom_start, custom_end = _pick_date_range(
                range_days, custom_start, custom_end
            )
        elif choice == "3":
            if not enabled:
                cprint("[yellow]No metrics selected. Toggle at least one metric first.[/yellow]")
                cinput("\nPress Enter to continue.")
            else:
                _render_chart(enabled, range_days, custom_start, custom_end, units)
        else:
            cprint("[yellow]Invalid choice. Press Enter to try again.[/yellow]")
            cinput("")


# ─────────────────────────────────────────────────────────────────────────────
# Header / status display
# ─────────────────────────────────────────────────────────────────────────────

def _render_trends_header(
    enabled: set[str],
    range_days: Optional[int],
    custom_start: Optional[date],
    custom_end: Optional[date],
    units: str,
) -> None:
    from rich.table import Table
    from core.console_manager import get_console

    console = get_console()

    table = Table(
        title="[bold]Trend Configuration[/bold]",
        show_header=True,
        header_style="bold",
        show_lines=False,
        title_justify="left",
    )
    table.add_column("Metric",    min_width=24)
    table.add_column("Status",    width=10, justify="center")
    table.add_column("Unit",      width=8,  justify="right")

    for key, label, u_metric, u_imperial, _ in _METRIC_DEFS:
        if key == "bp_diastolic":
            continue  # shown with systolic
        active = key in enabled or (key == "bp_systolic" and "bp_diastolic" in enabled)
        if key == "bp_systolic":
            label = "Blood Pressure"
        unit = u_imperial if units == "imperial" else u_metric
        style  = _METRIC_STYLE.get(key, "white")
        status = "[green]✔ ON[/green]" if active else "[dim]off[/dim]"
        table.add_row(f"[{style}]{label}[/{style}]", status, f"[dim]{unit}[/dim]")

    console.print(table)

    # Date range summary
    cprint("")
    range_str = _range_label(range_days, custom_start, custom_end)
    cprint(f"  [dim]Date range:[/dim]  [cyan]{range_str}[/cyan]")


def _range_label(
    range_days: Optional[int],
    custom_start: Optional[date],
    custom_end: Optional[date],
) -> str:
    if range_days is None and custom_start is None:
        return "All time"
    if custom_start is not None:
        end_str = custom_end.isoformat() if custom_end else date.today().isoformat()
        return f"{custom_start.isoformat()} → {end_str}"
    labels = {7: "Last 7 days", 30: "Last 30 days", 90: "Last 90 days"}
    return labels.get(range_days, f"Last {range_days} days")


# ─────────────────────────────────────────────────────────────────────────────
# Metric toggle sub-menu
# ─────────────────────────────────────────────────────────────────────────────

def _toggle_metrics_menu(enabled: set[str]) -> set[str]:
    """Let the user flip individual metrics on/off.  Returns updated set."""
    while True:
        clear_console()
        cprint("[bold]Toggle Metrics[/bold]\n")
        cprint("  [dim]Select a key to toggle. Enter [b] when done.[/dim]\n")

        for key, label in _TOGGLE_CHOICES:
            metrics = _TOGGLE_KEY_TO_METRICS[key]
            is_on   = any(m in enabled for m in metrics)
            status  = "[green]ON [/green]" if is_on else "[dim]off[/dim]"
            cprint(f"  [cyan]{key:>3}[/cyan])  {status}  {label}")

        cprint("")
        pick = cinput("Toggle (key) or [b] to finish: ").strip().lower()

        if pick == "b" or not pick:
            break
        if pick in _TOGGLE_KEY_TO_METRICS:
            metrics = _TOGGLE_KEY_TO_METRICS[pick]
            # If ANY of the group is on, turn the whole group OFF; else turn ON
            if any(m in enabled for m in metrics):
                enabled -= set(metrics)
            else:
                enabled |= set(metrics)
        else:
            cprint("[yellow]Unknown key.[/yellow]")
            cinput("Press Enter.")

    return enabled


# ─────────────────────────────────────────────────────────────────────────────
# Date-range picker
# ─────────────────────────────────────────────────────────────────────────────

def _pick_date_range(
    current_days: Optional[int],
    current_start: Optional[date],
    current_end: Optional[date],
) -> Tuple[Optional[int], Optional[date], Optional[date]]:
    clear_console()
    cprint("[bold]Date Range[/bold]\n")
    options = [
        ("1", "Last 7 days",   7),
        ("2", "Last 30 days",  30),
        ("3", "Last 90 days",  90),
        ("4", "All time",      None),
        ("5", "Custom range",  -1),
    ]
    for key, label, _ in options:
        cprint(f"  [cyan]{key}[/cyan])  {label}")
    cprint("")
    pick = cinput("Choice: ").strip()

    for key, _, val in options:
        if pick == key:
            if val == -1:
                return _prompt_custom_range()
            return val, None, None

    cprint("[yellow]Invalid — keeping current range.[/yellow]")
    cinput("Press Enter.")
    return current_days, current_start, current_end


def _prompt_custom_range() -> Tuple[Optional[int], Optional[date], Optional[date]]:
    today = date.today()
    cprint("\n[dim]Enter start date (YYYY-MM-DD) — blank = earliest data[/dim]")
    raw_start = cinput("Start: ").strip()
    start: Optional[date] = None
    if raw_start:
        try:
            start = date.fromisoformat(raw_start)
        except ValueError:
            cprint("[yellow]Couldn't parse start date — using earliest data.[/yellow]")

    cprint("[dim]Enter end date (YYYY-MM-DD) — blank = today[/dim]")
    raw_end = cinput("End: ").strip()
    end: Optional[date] = None
    if raw_end:
        try:
            end = date.fromisoformat(raw_end)
            if end > today:
                end = today
        except ValueError:
            cprint("[yellow]Couldn't parse end date — using today.[/yellow]")

    return None, start, end


# ─────────────────────────────────────────────────────────────────────────────
# Data loading + filtering
# ─────────────────────────────────────────────────────────────────────────────

def _date_bounds(
    range_days: Optional[int],
    custom_start: Optional[date],
    custom_end: Optional[date],
) -> Tuple[Optional[date], Optional[date]]:
    today = date.today()
    if custom_start is not None or (range_days is None and custom_start is None):
        # Custom or all-time
        return custom_start, custom_end or today
    # Preset
    return today - timedelta(days=range_days - 1), today


def _load_series(
    metrics: set[str],
    start: Optional[date],
    end: Optional[date],
    units: str,
) -> Dict[str, Tuple[List[str], List[float]]]:
    """
    Returns {metric_key: ([date_str, ...], [value, ...])} sorted by date.
    Values are converted to the user's display unit.
    """
    entries = _load_biometrics().get("entries", [])

    raw: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
    for e in entries:
        if e.get("metric") not in metrics:
            continue
        try:
            d = date.fromisoformat(e["date"])
        except (ValueError, KeyError):
            continue
        if start and d < start:
            continue
        if end and d > end:
            continue
        display_val = _to_display(e["value"], e["metric"], units)
        raw[e["metric"]].append((e["date"], display_val))

    # Sort and unzip
    result: Dict[str, Tuple[List[str], List[float]]] = {}
    for metric, pairs in raw.items():
        pairs.sort(key=lambda x: x[0])
        dates, vals = zip(*pairs)
        result[metric] = (list(dates), list(vals))

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Chart rendering
# ─────────────────────────────────────────────────────────────────────────────

def _render_chart(
    enabled: set[str],
    range_days: Optional[int],
    custom_start: Optional[date],
    custom_end: Optional[date],
    units: str,
) -> None:
    try:
        import plotly.graph_objects as go
    except ImportError:
        cprint("[red]Plotly is not installed. Run: pip install plotly[/red]")
        cinput("\nPress Enter to continue.")
        return

    start, end = _date_bounds(range_days, custom_start, custom_end)
    series = _load_series(enabled, start, end, units)

    if not series:
        cprint("[yellow]No data found for the selected metrics and date range.[/yellow]")
        cinput("\nPress Enter to continue.")
        return

    # Decide axis layout ---------------------------------------------------
    # "weight_like" metrics (weight, waist) on y2 when mixed with mmHg/bpm,
    # unless they're the only metrics shown.
    axis_groups = {m: _TREND_META[m][2] for m in series}
    unique_groups = set(axis_groups.values())
    use_secondary = len(unique_groups) > 1 and "weight_like" in unique_groups

    fig = go.Figure()

    weight_unit = "lbs" if units == "imperial" else "kg"
    waist_unit  = "in"  if units == "imperial" else "cm"

    for metric, (dates, vals) in series.items():
        label, color, group = _TREND_META[metric]
        yaxis = "y2" if (use_secondary and group == "weight_like") else "y"

        # Nicer label with unit
        unit_map = {
            "weight":       weight_unit,
            "bp_systolic":  "mmHg",
            "bp_diastolic": "mmHg",
            "heart_rate":   "bpm",
            "waist":        waist_unit,
            "body_fat_pct": "%",
        }
        unit = unit_map.get(metric, "")
        hover = f"%{{x}}<br>{label}: %{{y:.1f}} {unit}<extra></extra>"

        fig.add_trace(go.Scatter(
            x=dates,
            y=vals,
            mode="lines+markers",
            name=f"{label} ({unit})",
            line=dict(color=color, width=2),
            marker=dict(size=6, color=color),
            yaxis=yaxis,
            hovertemplate=hover,
        ))

    # Axis labels ----------------------------------------------------------
    primary_groups = [g for m, g in axis_groups.items() if
                      not (use_secondary and g == "weight_like")]
    secondary_groups = [g for m, g in axis_groups.items() if
                        use_secondary and g == "weight_like"] if use_secondary else []

    def _axis_label(groups: List[str]) -> str:
        labels = []
        if "pressure" in groups:
            labels.append("mmHg")
        if "rate" in groups:
            labels.append("bpm")
        if "percent" in groups:
            labels.append("%")
        if "weight_like" in groups:
            parts = []
            if "weight" in series:
                parts.append(weight_unit)
            if "waist" in series:
                parts.append(waist_unit)
            labels.append(" / ".join(parts))
        return " · ".join(labels)

    primary_label   = _axis_label(primary_groups)
    secondary_label = _axis_label(secondary_groups) if use_secondary else ""

    # Layout ---------------------------------------------------------------
    range_title = _range_label(range_days, custom_start, custom_end)
    metric_names = [_TREND_META[m][0] for m in series]
    chart_title  = "  ·  ".join(metric_names) + f"   [{range_title}]"

    layout_kwargs: Dict[str, Any] = dict(
        title=dict(text=chart_title, font=dict(size=16)),
        xaxis=dict(
            title="Date",
            tickangle=-30,
            showgrid=True,
            gridcolor="#2a2a2a",
        ),
        yaxis=dict(
            title=primary_label,
            showgrid=True,
            gridcolor="#2a2a2a",
            zeroline=False,
        ),
        plot_bgcolor="#1a1a2e",
        paper_bgcolor="#12121f",
        font=dict(color="#e0e0e0"),
        legend=dict(
            bgcolor="rgba(0,0,0,0.4)",
            bordercolor="#444",
            borderwidth=1,
        ),
        hovermode="x unified",
        margin=dict(l=60, r=60, t=70, b=60),
    )

    if use_secondary:
        layout_kwargs["yaxis2"] = dict(
            title=secondary_label,
            overlaying="y",
            side="right",
            showgrid=False,
            zeroline=False,
        )

    fig.update_layout(**layout_kwargs)

    # Add a shaded reference band for BP if both systolic & diastolic shown --
    if "bp_systolic" in series and "bp_diastolic" in series:
        fig.add_hrect(
            y0=90, y1=120,
            fillcolor="green", opacity=0.05,
            line_width=0,
            annotation_text="Normal BP range",
            annotation_position="right",
            annotation_font_color="#888",
            annotation_font_size=10,
        )

    # Render ---------------------------------------------------------------
    clear_console()
    cprint("[dim]Opening chart in browser…[/dim]")

    try:
        # Write to a temp HTML file and open in the default browser.
        # This is the most reliable cross-platform approach from a CLI app.
        with tempfile.NamedTemporaryFile(
            suffix=".html", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(fig.to_html(include_plotlyjs="cdn", full_html=True))
            tmp_path = f.name

        webbrowser.open(f"file://{tmp_path}")
        cprint(f"[green]✔ Chart opened in browser.[/green]")
        cprint(f"[dim]  (temp file: {tmp_path})[/dim]")
    except Exception as exc:
        cprint(f"[red]Failed to open browser: {exc}[/red]")
        cprint("[dim]Try installing a browser or checking your DISPLAY/BROWSER env vars.[/dim]")

    cinput("\nPress Enter to return to trends menu.")
