# src/core/dashboard_manager.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich import box

from core.health_manager import get_rmr_from_profile, get_tdee_from_rmr
from core.log_manager import get_daily_totals, get_latest_weight
from core.units import cm_to_in, kg_to_lb
from core.console_manager import get_console


# -------------------------------------------------
# Summary model
# -------------------------------------------------
@dataclass
class DailySummary:
    day: date

    calories_consumed: float
    calorie_target: float | None
    planned_delta: float | None          # calorie_target - tdee_estimate
    tdee_estimate: float | None
    rmr_estimate: float | None

    water_ml: float
    water_goal_ml: float

    current_weight_kg: float | None
    target_weight_kg: float | None
    start_weight_kg: float | None
    to_goal_kg: float | None
    total_change_kg: float | None

    @property
    def calorie_delta_from_target(self) -> float | None:
        if self.calorie_target is None:
            return None
        return self.calories_consumed - self.calorie_target


# -------------------------------------------------
# Styling / text helpers
# -------------------------------------------------
def _style_for_ratio(ratio: float, good_at_or_above: bool = True) -> str:
    if good_at_or_above:
        if ratio >= 1.0:
            return "green"
        if ratio >= 0.5:
            return "yellow"
        return "red"
    else:
        if ratio <= 1.0:
            return "green"
        if ratio <= 1.1:
            return "yellow"
        return "red"


def _calorie_style(consumed: float, target: float) -> str:
    if target <= 0:
        return "yellow"

    ratio = consumed / target
    if 0.95 <= ratio <= 1.05:
        return "green"
    if 0.90 <= ratio <= 1.10:
        return "yellow"
    return "red"


def _delta_text(delta: float) -> Text:
    if delta < 0:
        return Text(f"{delta:.0f} under", style="green")
    if delta > 0:
        return Text(f"+{delta:.0f} over", style="red")
    return Text("0 on target", style="green")


def _planned_text(delta: float) -> Text:
    if delta < 0:
        return Text(f"{delta:.0f} planned deficit", style="green")
    if delta > 0:
        return Text(f"+{delta:.0f} planned surplus", style="yellow")
    return Text("0 planned (maintain)", style="green")


def _default_water_goal_ml(sex_for_bmr: str) -> float:
    """
    Simple default hydration goal.
    Roughly based on commonly cited intake guidance:
    - male: 3.7 L/day
    - female: 2.7 L/day
    """
    sex = (sex_for_bmr or "").strip().lower()
    if sex == "male":
        return 3700.0
    if sex == "female":
        return 2700.0
    return 3200.0


# -------------------------------------------------
# Formatting helpers
# -------------------------------------------------
def _format_weight(weight_kg: float | None, units: str) -> str:
    if weight_kg is None:
        return "—"

    units = (units or "").strip().lower()
    if units == "imperial":
        weight_lb = kg_to_lb(weight_kg) 
        return f"{weight_lb:.1f} lb"
    return f"{weight_kg:.1f} kg"


def _format_water(water_ml: float, units: str) -> str:
    units = (units or "").strip().lower()
    if units == "imperial":
        oz = water_ml / 29.5735
        return f"{oz:.0f} oz"
    return f"{water_ml:.0f} mL"


# -------------------------------------------------
# Summary builder
# -------------------------------------------------
def build_daily_summary(env) -> DailySummary:
    profile = env.profile or {}
    goals = env.goals or {}
    config = env.config or {}
     
    totals = get_daily_totals(date.today())
    calories_consumed = totals["calories"]
    water_ml = totals["water_ml"]

    # -------------------------
    # RMR / TDEE
    # -------------------------
    try:
        rmr_estimate = float(get_rmr_from_profile(profile))
        tdee_estimate = float(get_tdee_from_rmr(rmr_estimate, profile["activity_level"]))
    except Exception:
        rmr_estimate = None
        tdee_estimate = None

    # -------------------------
    # Calorie target
    # -------------------------
    goal_type = str(goals.get("goal_type") or "").strip().lower()
    mode = str(config.get("calorie_target_mode") or "auto").strip().lower()

    calorie_target: float | None = None
    planned_delta: float | None = None

    if mode == "manual":
        manual = config.get("manual_calorie_target")
        try:
            calorie_target = float(manual) if manual is not None else None
        except (TypeError, ValueError):
            calorie_target = None
    else:
        weekly_rate = goals.get("weekly_rate")
        try:
            weekly_rate = float(weekly_rate) if weekly_rate is not None else 0.0
        except (TypeError, ValueError):
            weekly_rate = 0.0

        # Assumes weekly_rate is stored canonically as kg/week.
        # ~7700 kcal per kg => ~1100 kcal/day per kg/week.
        daily_delta = weekly_rate * 7700.0 / 7.0

        if tdee_estimate is not None:
            if goal_type == "lose":
                calorie_target = tdee_estimate - daily_delta
            elif goal_type == "gain":
                calorie_target = tdee_estimate + daily_delta
            elif goal_type == "maintain":
                calorie_target = tdee_estimate

    if calorie_target is not None and tdee_estimate is not None:
        planned_delta = calorie_target - tdee_estimate

    # -------------------------
    # Water
    # -------------------------
    water_goal_ml = float(config.get("water_goal_ml") or _default_water_goal_ml(profile.get("sex_for_bmr", "")))

    # -------------------------
    # Weights
    # -------------------------
    def _safe_float(value) -> float | None:
        try:
            return float(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    # Prefer today's logged weight; fall back to profile's stored weight
    logged_weight_today = get_latest_weight(date.today())
    current_weight_kg = logged_weight_today if logged_weight_today is not None else _safe_float(profile.get("weight_kg"))
    target_weight_kg = _safe_float(goals.get("target_weight"))
    start_weight_kg = _safe_float(goals.get("start_weight"))

    to_goal_kg: float | None = None
    total_change_kg: float | None = None

    if current_weight_kg is not None and target_weight_kg is not None:
        to_goal_kg = target_weight_kg - current_weight_kg

    if current_weight_kg is not None and start_weight_kg is not None:
        total_change_kg = current_weight_kg - start_weight_kg

    return DailySummary(
        day=date.today(),
        calories_consumed=calories_consumed,
        calorie_target=calorie_target,
        planned_delta=planned_delta,
        tdee_estimate=tdee_estimate,
        rmr_estimate=rmr_estimate,
        water_ml=water_ml,
        water_goal_ml=water_goal_ml,
        current_weight_kg=current_weight_kg,
        target_weight_kg=target_weight_kg,
        start_weight_kg=start_weight_kg,
        to_goal_kg=to_goal_kg,
        total_change_kg=total_change_kg,
    )


# -------------------------------------------------
# Progress bar helper
# -------------------------------------------------
_BAR_WIDTH = 18

def _progress_bar(ratio: float, style: str) -> Text:
    """Render a fixed-width unicode block progress bar."""
    ratio = max(0.0, min(ratio, 1.0))
    filled = round(ratio * _BAR_WIDTH)
    empty  = _BAR_WIDTH - filled
    bar = Text()
    bar.append("#" * filled, style=style)
    bar.append("-" * empty,  style="bright_black")
    bar.append(f"  {ratio:.0%}", style=style)
    return bar


def _label(text: str) -> Text:
    """Dim label so values stand out more clearly."""
    return Text(text, style="dim")


# -------------------------------------------------
# Renderer
# -------------------------------------------------
def render_dashboard(summary: DailySummary, units: str, console: Console | None = None) -> None:
    if console is None:
        import shutil
        columns, _ = shutil.get_terminal_size(fallback=(120, 50))
        console = Console(width=min(columns, 180))
    
    

    # ── Header ────────────────────────────────────────────────────────────────
    header = Text()
    header.append("  Daily Dashboard", style="bold white")
    header.append("  •  ", style="bright_black")
    day_str = f"{summary.day.strftime('%A, %B')} {summary.day.day} {summary.day.strftime('%Y')}"
    header.append(day_str, style="bright_black")

    console.print(Panel(header, border_style="bright_magenta", box=box.ROUNDED, padding=(0, 1)))

    # ── Calories panel ────────────────────────────────────────────────────────
    cal_table = Table.grid(padding=(0, 2))
    cal_table.add_column(justify="left",  no_wrap=True)
    cal_table.add_column(justify="right", no_wrap=True)

    cal_table.add_row(
        _label("Consumed"),
        Text(f"{summary.calories_consumed:.0f} kcal", style="bold white"),
    )

    if summary.calorie_target is None:
        cal_table.add_row(_label("Target"), Text("—", style="bright_black"))
    else:
        style = _calorie_style(summary.calories_consumed, summary.calorie_target)
        ratio = summary.calories_consumed / summary.calorie_target if summary.calorie_target else 0.0

        cal_table.add_row(
            _label("Target"),
            Text(f"{summary.calorie_target:.0f} kcal", style="white"),
        )
        cal_table.add_row(_label("Progress"), _progress_bar(ratio, style))

        delta = summary.calorie_delta_from_target
        if delta is not None:
            cal_table.add_row(_label("Delta"), _delta_text(delta))

    cal_table.add_row(_label(""), Text(""))   # spacer

    tdee_val = f"{summary.tdee_estimate:.0f}" if summary.tdee_estimate is not None else "—"
    rmr_val  = f"{summary.rmr_estimate:.0f}"  if summary.rmr_estimate  is not None else "—"
    cal_table.add_row(_label("TDEE est."), Text(tdee_val, style="cyan"))
    cal_table.add_row(_label("RMR est."),  Text(rmr_val,  style="cyan"))

    if summary.planned_delta is not None:
        cal_table.add_row(_label("Plan"), _planned_text(summary.planned_delta))

    calories_panel = Panel(
        cal_table,
        title="[bold cyan]Calories[/bold cyan]",
        border_style="cyan",
        box=box.ROUNDED,
        padding=(0, 1),
    )

    # ── Hydration panel ───────────────────────────────────────────────────────
    water_ratio = summary.water_ml / summary.water_goal_ml if summary.water_goal_ml > 0 else 0.0
    water_style = _style_for_ratio(water_ratio, good_at_or_above=True)

    water_table = Table.grid(padding=(0, 2))
    water_table.add_column(justify="left",  no_wrap=True)
    water_table.add_column(justify="right", no_wrap=True)

    water_table.add_row(
        _label("Consumed"),
        Text(_format_water(summary.water_ml, units), style="bold white"),
    )
    water_table.add_row(
        _label("Goal"),
        Text(_format_water(summary.water_goal_ml, units), style="white"),
    )
    water_table.add_row(_label("Progress"), _progress_bar(water_ratio, water_style))

    water_panel = Panel(
        water_table,
        title="[bold blue]Hydration[/bold blue]",
        border_style="blue",
        box=box.ROUNDED,
        padding=(0, 1),
    )

    # ── Weight panel ──────────────────────────────────────────────────────────
    weight_table = Table.grid(padding=(0, 2))
    weight_table.add_column(justify="left",  no_wrap=True)
    weight_table.add_column(justify="right", no_wrap=True)

    weight_table.add_row(
        _label("Current"),
        Text(_format_weight(summary.current_weight_kg, units), style="bold white"),
    )
    weight_table.add_row(
        _label("Target"),
        Text(_format_weight(summary.target_weight_kg, units), style="white"),
    )
    weight_table.add_row(
        _label("Start"),
        Text(_format_weight(summary.start_weight_kg, units), style="white"),
    )

    weight_table.add_row(_label(""), Text(""))   # spacer

    # Colour to-goal by direction: green moving toward target, red moving away
    if summary.to_goal_kg is not None:
        goal_type_sign = -1 if (summary.target_weight_kg or 0) < (summary.current_weight_kg or 0) else 1
        to_goal_style = "green" if (summary.to_goal_kg * goal_type_sign) <= 0 else "yellow"
    else:
        to_goal_style = "white"

    # Colour total change the same way
    if summary.total_change_kg is not None:
        change_style = "green" if summary.total_change_kg * goal_type_sign <= 0 else "red"
        change_prefix = "+" if summary.total_change_kg > 0 else ""
        change_str = f"{change_prefix}{_format_weight(summary.total_change_kg, units)}"
    else:
        change_style = "bright_black"
        change_str = "—"

    weight_table.add_row(
        _label("To goal"),
        Text(_format_weight(summary.to_goal_kg, units), style=to_goal_style),
    )
    weight_table.add_row(
        _label("Change"),
        Text(change_str, style=change_style),
    )

    weight_panel = Panel(
        weight_table,
        title="[bold green]Weight[/bold green]",
        border_style="green",
        box=box.ROUNDED,
        padding=(0, 1),
    )

    # ── Layout: all three panels in a fixed-height table row ─────────────────
    layout = Table.grid(expand=True)
    layout.add_column(ratio=1)
    layout.add_column(ratio=1)
    layout.add_column(ratio=1)
    layout.add_row(calories_panel, water_panel, weight_panel)

    console.print(layout)
    console.print()


def render_main_dashboard(env, console: Console | None = None) -> None:
    summary = build_daily_summary(env)
    units = str(env.config.get("units", "metric")).strip().lower()
    render_dashboard(summary, units, console=console)