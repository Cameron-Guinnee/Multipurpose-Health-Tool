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

from core.health_manager import get_rmr_from_profile, get_tdee_from_rmr
from core.units import metric_to_imperial


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
        weight_lb, _ = metric_to_imperial(weight_kg, 0.0)
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

    calories_consumed = float(config.get("_debug_calories_consumed", 0.0))
    water_ml = float(config.get("_debug_water_ml", 0.0))

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
    mode = str(goals.get("calorie_target_mode") or "auto").strip().lower()

    calorie_target: float | None = None
    planned_delta: float | None = None

    if mode == "manual":
        manual = goals.get("manual_calorie_target")
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

    current_weight_kg = _safe_float(profile.get("weight_kg"))
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
# Renderer
# -------------------------------------------------
def render_dashboard(summary: DailySummary, units: str, console: Console | None = None) -> None:
    console = console or Console()

    # Calories panel
    cal_table = Table.grid(padding=(0, 1))
    cal_table.add_column(justify="left")
    cal_table.add_column(justify="right")

    cal_table.add_row("Calories consumed", f"{summary.calories_consumed:.0f}")

    if summary.calorie_target is None:
        cal_table.add_row("Target", "—")
        cal_table.add_row("Status", "No target")
    else:
        style = _calorie_style(summary.calories_consumed, summary.calorie_target)
        cal_table.add_row("Target", f"{summary.calorie_target:.0f}")
        cal_table.add_row(
            "Status",
            Text.from_markup(f"[{style}]{summary.calories_consumed:.0f} / {summary.calorie_target:.0f}[/{style}]"),
        )
        delta = summary.calorie_delta_from_target
        if delta is not None:
            cal_table.add_row("Delta", _delta_text(delta))

    if summary.tdee_estimate is not None:
        cal_table.add_row("TDEE est.", f"{summary.tdee_estimate:.0f}")
    else:
        cal_table.add_row("TDEE est.", "—")

    if summary.rmr_estimate is not None:
        cal_table.add_row("RMR est.", f"{summary.rmr_estimate:.0f}")
    else:
        cal_table.add_row("RMR est.", "—")

    if summary.planned_delta is not None:
        cal_table.add_row("Plan", _planned_text(summary.planned_delta))

    calories_panel = Panel(cal_table, title="Calories", border_style="cyan")

    # Water panel
    water_ratio = summary.water_ml / summary.water_goal_ml if summary.water_goal_ml > 0 else 0.0
    water_style = _style_for_ratio(water_ratio, good_at_or_above=True)

    water_table = Table.grid(padding=(0, 1))
    water_table.add_column(justify="left")
    water_table.add_column(justify="right")
    water_table.add_row("Consumed", _format_water(summary.water_ml, units))
    water_table.add_row("Goal", _format_water(summary.water_goal_ml, units))
    water_table.add_row("Progress", Text(f"{water_ratio:.0%}", style=water_style))

    water_panel = Panel(water_table, title="Hydration", border_style="blue")

    # Weight panel
    weight_table = Table.grid(padding=(0, 1))
    weight_table.add_column(justify="left")
    weight_table.add_column(justify="right")
    weight_table.add_row("Current", _format_weight(summary.current_weight_kg, units))
    weight_table.add_row("Target", _format_weight(summary.target_weight_kg, units))
    weight_table.add_row("Start", _format_weight(summary.start_weight_kg, units))
    weight_table.add_row("To goal", _format_weight(summary.to_goal_kg, units))
    weight_table.add_row("Change", _format_weight(summary.total_change_kg, units))

    weight_panel = Panel(weight_table, title="Weight", border_style="green")

    console.print(
        Panel(
            f"[bold]Daily Dashboard[/bold] • {summary.day.isoformat()}",
            border_style="magenta",
        )
    )
    console.print(Columns([calories_panel, water_panel, weight_panel], equal=True, expand=True))


def render_main_dashboard(env, console: Console | None = None) -> None:
    summary = build_daily_summary(env)
    units = str(env.config.get("units", "metric")).strip().lower()
    render_dashboard(summary, units, console=console)