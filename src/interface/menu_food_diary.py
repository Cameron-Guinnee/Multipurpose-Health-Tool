from __future__ import annotations

from datetime import date
from typing import List

from rich.table import Table
from rich.console import Console

from interface.prompts import _prompt_str, _prompt_float, _prompt_choice

from core.console_manager import cprint, cinput, clear_console
from core.data_manager import Environment
from core.log_manager import (
    append_entry,
    delete_entry,
    load_day,
    make_food_entry,
    make_water_entry,
    get_daily_totals,
)



MEAL_CATEGORIES = ("breakfast", "lunch", "dinner", "snack", "uncategorized")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def run_food_diary_menu(env: Environment) -> None:
    units = str(env.config.get("units", "imperial")).strip().lower()

    while True:
        clear_console()
        today = date.today()
        _render_food_diary(today, units)

        cprint("\n[bold purple]Food Diary[/bold purple]")
        cprint("[dim]Select an option:[/dim]\n")
        cprint("  [cyan]1[/cyan]) Log food")
        cprint("  [cyan]2[/cyan]) Log water")
        cprint("  [cyan]3[/cyan]) Delete a food entry")
        cprint("  [cyan]b[/cyan]) Back")

        choice = cinput("\nChoice: ").strip().lower()

        if choice == "1":
            _log_food(today)
        elif choice == "2":
            _log_water(today, units)
        elif choice == "3":
            _delete_food(today)
        elif choice == "b":
            return
        else:
            cprint("[yellow]Invalid choice. Press Enter to try again.[/yellow]")
            cinput("")


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------
def _render_food_diary(d: date, units: str) -> None:
    console = Console()
    day = load_day(d)
    totals = get_daily_totals(d)

    food_entries = day.get("food_entries", [])
    water_entries = day.get("water_entries", [])

    # --- Food table ---
    food_table = Table(title=f"Food Log — {d.isoformat()}", show_lines=False)
    food_table.add_column("ID", style="dim", width=6)
    food_table.add_column("Meal", style="cyan", width=12)
    food_table.add_column("Food", width=24)
    food_table.add_column("Qty", justify="right", width=8)
    food_table.add_column("Cal", justify="right", width=7)
    food_table.add_column("P (g)", justify="right", width=7)
    food_table.add_column("C (g)", justify="right", width=7)
    food_table.add_column("F (g)", justify="right", width=7)

    for e in food_entries:
        food_table.add_row(
            e.get("id", "?"),
            e.get("meal_category", "—").capitalize(),
            e.get("name", "—"),
            f"{e.get('quantity', 1):.1f} {e.get('unit', '')}",
            str(int(e.get("calories", 0))),
            str(e.get("protein_g", 0)),
            str(e.get("carbs_g", 0)),
            str(e.get("fat_g", 0)),
        )

    if food_entries:
        food_table.add_section()
        food_table.add_row(
            "", "", "[bold]Total[/bold]", "",
            f"[bold]{int(totals['calories'])}[/bold]",
            f"[bold]{totals['protein_g']}[/bold]",
            f"[bold]{totals['carbs_g']}[/bold]",
            f"[bold]{totals['fat_g']}[/bold]",
        )

    console.print(food_table)

    # --- Water summary ---
    if units == "imperial":
        consumed = totals["water_ml"] / 29.5735
        entries_fmt = [f"{e['amount_ml'] / 29.5735:.0f} oz" for e in water_entries]
        water_str = f"{consumed:.0f} oz"
    else:
        consumed = totals["water_ml"]
        entries_fmt = [f"{e['amount_ml']:.0f} mL" for e in water_entries]
        water_str = f"{consumed:.0f} mL"

    if entries_fmt:
        cprint(f"[bold]Water:[/bold] {water_str}  [dim]({', '.join(entries_fmt)})[/dim]")
    else:
        cprint(f"[bold]Water:[/bold] {water_str}  [dim](none logged)[/dim]")


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------
def _log_food(d: date) -> None:
    clear_console()
    cprint("[bold]Log Food[/bold]\n")

    name = _prompt_str("Food name: ")
    if not name:
        return

    meal_category = _prompt_choice(
        f"Meal category ({'/'.join(MEAL_CATEGORIES)}): ",
        choices=MEAL_CATEGORIES,
        default="uncategorized",
    )

    quantity = _prompt_float("Quantity (e.g. 1.5): ", min_=0.01, default=1.0)
    unit = _prompt_str("Unit (e.g. cup, g, oz, serving): ", default="serving")
    calories = _prompt_float("Calories: ", min_=0.0, default=0.0)
    protein_g = _prompt_float("Protein (g): ", min_=0.0, default=0.0)
    carbs_g = _prompt_float("Carbs (g): ", min_=0.0, default=0.0)
    fat_g = _prompt_float("Fat (g): ", min_=0.0, default=0.0)

    entry = make_food_entry(
        name=name,
        calories=calories,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        quantity=quantity,
        unit=unit,
        meal_category=meal_category,
    )
    append_entry(d, "food_entries", entry)
    cprint(f"[green]✔ Logged {name} ({int(calories)} kcal)[/green]")
    cinput("\nPress Enter to continue.")


def _log_water(d: date, units: str) -> None:
    clear_console()
    cprint("[bold]Log Water[/bold]\n")

    if units == "imperial":
        oz = _prompt_float("Amount (oz): ", min_=0.1)
        amount_ml = oz * 29.5735
        display = f"{oz:.0f} oz"
    else:
        amount_ml = _prompt_float("Amount (mL): ", min_=1.0)
        display = f"{amount_ml:.0f} mL"

    entry = make_water_entry(amount_ml)
    append_entry(d, "water_entries", entry)
    cprint(f"[green]✔ Logged {display} of water[/green]")
    cinput("\nPress Enter to continue.")


def _delete_food(d: date) -> None:
    clear_console()
    day = load_day(d)
    entries = day.get("food_entries", [])

    if not entries:
        cprint("[yellow]No food entries to delete.[/yellow]")
        cinput("\nPress Enter to continue.")
        return

    cprint("[bold]Delete Food Entry[/bold]\n")
    for e in entries:
        cprint(f"  [cyan]{e['id']}[/cyan]  {e['name']} — {int(e.get('calories', 0))} kcal ({e.get('meal_category', '').capitalize()})")

    entry_id = cinput("\nEnter ID to delete (or blank to cancel): ").strip()
    if not entry_id:
        return

    removed = delete_entry(d, "food_entries", entry_id)
    if removed:
        cprint("[green]✔ Entry deleted.[/green]")
    else:
        cprint("[yellow]No entry found with that ID.[/yellow]")
    cinput("\nPress Enter to continue.")
