from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any, Dict, List, Optional

from rich.table import Table
from rich.console import Console

from interface.prompts import _prompt_str, _prompt_float, _prompt_choice

from core.console_manager import cprint, cinput, clear_console
from core.data_manager import (
    Environment,
    CUSTOM_FOODS_PATH,
    _atomic_write_json,
)
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
# Custom foods persistence
# ---------------------------------------------------------------------------

def _load_custom_foods() -> List[Dict[str, Any]]:
    """Return the list of saved custom food items."""
    if not CUSTOM_FOODS_PATH.exists():
        return []
    try:
        with CUSTOM_FOODS_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        foods = data.get("foods", [])
        return foods if isinstance(foods, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_custom_foods(foods: List[Dict[str, Any]]) -> None:
    """Persist the custom foods list atomically."""
    _atomic_write_json(CUSTOM_FOODS_PATH, {"foods": foods})


def _make_custom_food(
    name: str,
    calories: float,
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    unit: str,
    quantity: float,
) -> Dict[str, Any]:
    return {
        "id": uuid.uuid4().hex[:8],
        "name": name.strip(),
        "calories": round(calories, 1),
        "protein_g": round(protein_g, 1),
        "carbs_g": round(carbs_g, 1),
        "fat_g": round(fat_g, 1),
        "unit": unit.strip(),
        "quantity": quantity,
    }


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
        cprint("  [cyan]4[/cyan]) Manage custom foods")
        cprint("  [cyan]b[/cyan]) Back")

        choice = cinput("\nChoice: ").strip().lower()

        if choice == "1":
            _log_food(today)
        elif choice == "2":
            _log_water(today, units)
        elif choice == "3":
            _delete_food(today)
        elif choice == "4":
            _manage_custom_foods_menu()
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


def _render_custom_foods_table(foods: List[Dict[str, Any]]) -> None:
    """Print a numbered table of all custom food items."""
    console = Console()
    table = Table(title="Custom Foods", show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("Name", width=24)
    table.add_column("Qty / Unit", justify="right", width=12)
    table.add_column("Cal", justify="right", width=7)
    table.add_column("P (g)", justify="right", width=7)
    table.add_column("C (g)", justify="right", width=7)
    table.add_column("F (g)", justify="right", width=7)

    for i, f in enumerate(foods, start=1):
        table.add_row(
            str(i),
            f.get("name", "—"),
            f"{f.get('quantity', 1):.1f} {f.get('unit', '')}",
            str(int(f.get("calories", 0))),
            str(f.get("protein_g", 0)),
            str(f.get("carbs_g", 0)),
            str(f.get("fat_g", 0)),
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Custom foods management submenu
# ---------------------------------------------------------------------------

def _manage_custom_foods_menu() -> None:
    while True:
        clear_console()
        foods = _load_custom_foods()

        if foods:
            _render_custom_foods_table(foods)
        else:
            cprint("[dim]No custom foods defined yet.[/dim]\n")

        cprint("\n[bold purple]Manage Custom Foods[/bold purple]")
        cprint("[dim]Select an option:[/dim]\n")
        cprint("  [cyan]1[/cyan]) Add a custom food")
        if foods:
            cprint("  [cyan]2[/cyan]) Edit a custom food")
            cprint("  [cyan]3[/cyan]) Delete a custom food")
        cprint("  [cyan]b[/cyan]) Back")

        choice = cinput("\nChoice: ").strip().lower()

        if choice == "1":
            _add_custom_food(foods)
        elif choice == "2" and foods:
            _edit_custom_food(foods)
        elif choice == "3" and foods:
            _delete_custom_food(foods)
        elif choice == "b":
            return
        else:
            cprint("[yellow]Invalid choice. Press Enter to try again.[/yellow]")
            cinput("")


def _prompt_food_fields(
    name_default: str = "",
    calories_default: float = 0.0,
    protein_default: float = 0.0,
    carbs_default: float = 0.0,
    fat_default: float = 0.0,
    unit_default: str = "serving",
    quantity_default: float = 1.0,
) -> Optional[Dict[str, Any]]:
    """Prompt for all nutrition fields. Returns None if the user cancels."""
    name = _prompt_str("Food name: ", default=name_default)
    if not name:
        return None

    quantity = _prompt_float("Quantity (e.g. 1.5): ", min_=0.01, default=quantity_default)
    unit = _prompt_str("Unit (e.g. cup, g, oz, serving): ", default=unit_default)
    calories = _prompt_float("Calories: ", min_=0.0, default=calories_default)
    protein_g = _prompt_float("Protein (g): ", min_=0.0, default=protein_default)
    carbs_g = _prompt_float("Carbs (g): ", min_=0.0, default=carbs_default)
    fat_g = _prompt_float("Fat (g): ", min_=0.0, default=fat_default)

    return dict(
        name=name,
        calories=calories,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        unit=unit,
        quantity=quantity,
    )


def _add_custom_food(foods: List[Dict[str, Any]]) -> None:
    clear_console()
    cprint("[bold]Add Custom Food[/bold]\n")

    fields = _prompt_food_fields()
    if fields is None:
        return

    food = _make_custom_food(**fields)
    foods.append(food)
    _save_custom_foods(foods)
    cprint(f"[green]✔ '{food['name']}' saved to custom foods.[/green]")
    cinput("\nPress Enter to continue.")


def _edit_custom_food(foods: List[Dict[str, Any]]) -> None:
    clear_console()
    _render_custom_foods_table(foods)
    cprint("\n[bold]Edit Custom Food[/bold]")

    raw = cinput("\nEnter number to edit (or blank to cancel): ").strip()
    if not raw:
        return
    try:
        idx = int(raw) - 1
        if not (0 <= idx < len(foods)):
            raise ValueError
    except ValueError:
        cprint("[yellow]Invalid selection.[/yellow]")
        cinput("\nPress Enter to continue.")
        return

    existing = foods[idx]
    cprint(f"\n[dim]Editing '{existing['name']}' — press Enter to keep current value.[/dim]\n")

    fields = _prompt_food_fields(
        name_default=existing.get("name", ""),
        calories_default=existing.get("calories", 0.0),
        protein_default=existing.get("protein_g", 0.0),
        carbs_default=existing.get("carbs_g", 0.0),
        fat_default=existing.get("fat_g", 0.0),
        unit_default=existing.get("unit", "serving"),
        quantity_default=existing.get("quantity", 1.0),
    )
    if fields is None:
        return

    # Preserve the original ID so diary logs aren't affected
    updated = _make_custom_food(**fields)
    updated["id"] = existing["id"]
    foods[idx] = updated
    _save_custom_foods(foods)
    cprint(f"[green]✔ '{updated['name']}' updated.[/green]")
    cinput("\nPress Enter to continue.")


def _delete_custom_food(foods: List[Dict[str, Any]]) -> None:
    clear_console()
    _render_custom_foods_table(foods)
    cprint("\n[bold]Delete Custom Food[/bold]")

    raw = cinput("\nEnter number to delete (or blank to cancel): ").strip()
    if not raw:
        return
    try:
        idx = int(raw) - 1
        if not (0 <= idx < len(foods)):
            raise ValueError
    except ValueError:
        cprint("[yellow]Invalid selection.[/yellow]")
        cinput("\nPress Enter to continue.")
        return

    removed = foods.pop(idx)
    _save_custom_foods(foods)
    cprint(f"[green]✔ '{removed['name']}' deleted.[/green]")
    cinput("\nPress Enter to continue.")


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def _log_food(d: date) -> None:
    clear_console()
    cprint("[bold]Log Food[/bold]\n")

    custom_foods = _load_custom_foods()

    # --- Offer quick-pick from custom foods if any are defined ---
    if custom_foods:
        _render_custom_foods_table(custom_foods)
        cprint("\n[dim]Enter a number to log a custom food, or press Enter to enter manually.[/dim]")
        raw = cinput("Selection: ").strip()

        if raw:
            try:
                idx = int(raw) - 1
                if not (0 <= idx < len(custom_foods)):
                    raise ValueError
            except ValueError:
                cprint("[yellow]Invalid selection — falling back to manual entry.[/yellow]\n")
            else:
                template = custom_foods[idx]
                _log_food_from_template(d, template)
                return

    # --- Manual entry ---
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


def _log_food_from_template(d: date, template: Dict[str, Any]) -> None:
    """Log a diary entry pre-filled from a custom food template.

    The user can adjust the quantity (and therefore scale all macros) and
    choose a meal category, but nutritional values per unit come from the
    template so they don't have to retype them.
    """
    cprint(f"\n[bold]{template['name']}[/bold]  "
           f"[dim]{int(template['calories'])} kcal / "
           f"{template['quantity']} {template['unit']}[/dim]\n")

    meal_category = _prompt_choice(
        f"Meal category ({'/'.join(MEAL_CATEGORIES)}): ",
        choices=MEAL_CATEGORIES,
        default="uncategorized",
    )

    base_qty = template.get("quantity", 1.0)
    quantity = _prompt_float(
        f"Quantity [{template['unit']}] (default {base_qty}): ",
        min_=0.01,
        default=base_qty,
    )

    # Scale macros proportionally when quantity differs from the template base
    scale = quantity / base_qty if base_qty else 1.0
    calories = template.get("calories", 0.0) * scale
    protein_g = template.get("protein_g", 0.0) * scale
    carbs_g = template.get("carbs_g", 0.0) * scale
    fat_g = template.get("fat_g", 0.0) * scale

    entry = make_food_entry(
        name=template["name"],
        calories=calories,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        quantity=quantity,
        unit=template.get("unit", "serving"),
        meal_category=meal_category,
    )
    append_entry(d, "food_entries", entry)
    cprint(f"[green]✔ Logged {template['name']} ({int(calories)} kcal)[/green]")
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