from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from rich.table import Table
from rich.text import Text

from interface.prompts import _prompt_str, _prompt_float, _prompt_choice

from core.console_manager import cprint, cinput, clear_console, get_console
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
    get_daily_totals,
)
from core.fdc_importer import search_foods, db_stats
from core.data_manager import DATA_DIR

FDC_DB_PATH = DATA_DIR / "fdc" / "fdc.db"
_FDC_SEARCH_LIMIT = 15


MEAL_CATEGORIES = ("breakfast", "lunch", "dinner", "snack", "drink", "uncategorized")

_CATEGORY_STYLE: Dict[str, str] = {
    "breakfast":    "yellow",
    "lunch":        "green",
    "dinner":       "cyan",
    "snack":        "magenta",
    "drink":        "blue",
    "uncategorized":"dim",
}

_CATEGORY_ORDER = ["breakfast", "lunch", "dinner", "snack", "drink", "uncategorized"]


# ---------------------------------------------------------------------------
# Custom foods persistence
# ---------------------------------------------------------------------------

def _load_custom_foods() -> List[Dict[str, Any]]:
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
    _atomic_write_json(CUSTOM_FOODS_PATH, {"foods": foods})


def _make_custom_food(
    name: str,
    calories: float,
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    unit: str,
    quantity: float,
    is_drink: bool = False,
    volume_ml_per_unit: Optional[float] = None,
) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "id": uuid.uuid4().hex[:8],
        "name": name.strip(),
        "calories": round(calories, 1),
        "protein_g": round(protein_g, 1),
        "carbs_g": round(carbs_g, 1),
        "fat_g": round(fat_g, 1),
        "unit": unit.strip(),
        "quantity": quantity,
        "is_drink": is_drink,
    }
    if is_drink and volume_ml_per_unit is not None:
        entry["volume_ml_per_unit"] = round(volume_ml_per_unit, 1)
    return entry


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_food_diary_menu(env: Environment) -> None:
    units = str(env.config.get("units", "imperial")).strip().lower()
    viewed_date = date.today()

    while True:
        clear_console()
        today = date.today()
        _render_food_diary(viewed_date, units)

        # Navigation hint line
        is_today = viewed_date == today
        nav_next = "[cyan]>[/cyan] next day" if not is_today else "[dim]> next day[/dim]"
        nav_today = "  [cyan]t[/cyan] today" if not is_today else ""
        cprint(f"\n  [cyan]<[/cyan] prev day    {nav_next}    [cyan]g[/cyan] go to date{nav_today}")

        cprint("\n[bold purple]Food Diary[/bold purple]")
        cprint("[dim]Select an option:[/dim]\n")
        cprint("  [cyan]1[/cyan]) Log food or drink")
        cprint("  [cyan]2[/cyan]) Delete an entry")
        cprint("  [cyan]3[/cyan]) Manage custom foods")
        cprint("  [cyan]b[/cyan]) Back")

        choice = cinput("\nChoice: ").strip().lower()

        if choice == "1":
            _log_entry(viewed_date, units)
        elif choice == "2":
            _delete_food(viewed_date)
        elif choice == "3":
            _manage_custom_foods_menu(units)
        elif choice == "<":
            viewed_date -= timedelta(days=1)
        elif choice == ">":
            if viewed_date < today:
                viewed_date += timedelta(days=1)
        elif choice == "t":
            viewed_date = today
        elif choice == "g":
            jumped = _prompt_date(today)
            if jumped is not None:
                viewed_date = jumped
        elif choice == "b":
            return
        else:
            cprint("[yellow]Invalid choice. Press Enter to try again.[/yellow]")
            cinput("")

# ---------------------------------------------------------------------------
# Date navigation
# ---------------------------------------------------------------------------

def _prompt_date(today: date) -> Optional[date]:
    """Prompt the user to enter a date and return it, or None on cancel.

    Accepts: YYYY-MM-DD, MM-DD, or MM/DD (assumes current year).
    Rejects future dates.
    """
    cprint("\n[dim]Enter a date — formats: YYYY-MM-DD, MM-DD, or MM/DD (blank to cancel)[/dim]")
    raw = cinput("Date: ").strip()
    if not raw:
        return None

    parsed: Optional[date] = None
    normalized = raw.replace("/", "-")

    for fmt in ("%Y-%m-%d", "%m-%d"):
        try:
            if fmt == "%m-%d":
                # Assume current year
                parsed = date.fromisoformat(f"{today.year}-{normalized}")
            else:
                parsed = date.fromisoformat(normalized)
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

def _render_food_diary(d: date, units: str) -> None:
    console = get_console()
    day = load_day(d)
    totals = get_daily_totals(d)

    food_entries = day.get("food_entries", [])

    # Group entries by meal category
    grouped: Dict[str, List[Dict[str, Any]]] = {cat: [] for cat in _CATEGORY_ORDER}
    for e in food_entries:
        cat = e.get("meal_category", "uncategorized")
        if cat not in grouped:
            cat = "uncategorized"
        grouped[cat].append(e)

    today = date.today()
    delta = (today - d).days
    if delta == 0:
        date_label = f"{d.strftime('%A, %B')} {d.day} [green]· today[/green]"
    elif delta == 1:
        date_label = f"{d.strftime('%A, %B')} {d.day} [yellow]· yesterday[/yellow]"
    else:
        date_label = f"{d.strftime('%A, %B')} {d.day} [yellow]· {delta} days ago[/yellow]"

    food_table = Table(
        title=f"[bold]Food & Drink Log[/bold]  [dim]{date_label}[/dim]",
        show_lines=False,
        show_header=True,
        header_style="bold",
        title_justify="left",
    )
    food_table.add_column("ID",   style="dim", width=6,  no_wrap=True)
    food_table.add_column("Meal", width=11, no_wrap=True)
    food_table.add_column("Item", min_width=20, max_width=32)
    food_table.add_column("Qty",  justify="right", width=12, no_wrap=True)
    food_table.add_column("kcal", justify="right", width=6,  no_wrap=True)
    food_table.add_column("P(g)",    justify="right", width=5,  no_wrap=True)
    food_table.add_column("C(g)",    justify="right", width=5,  no_wrap=True)
    food_table.add_column("F(g)",    justify="right", width=5,  no_wrap=True)

    any_entries = any(grouped[cat] for cat in _CATEGORY_ORDER)

    if not any_entries:
        food_table.add_row("[dim]—[/dim]", "[dim]Nothing logged yet[/dim]", "", "", "", "", "", "")
    else:
        first_section = True
        for cat in _CATEGORY_ORDER:
            entries = grouped[cat]
            if not entries:
                continue

            if not first_section:
                food_table.add_row("", "", "", "", "", "", "", "")
            first_section = False

            cat_style = _CATEGORY_STYLE.get(cat, "white")

            for e in entries:
                qty_str = f"{e.get('quantity', 1):.1f} {e.get('unit', '')}".strip()
                if e.get("meal_category") == "drink" and "amount_ml" in e:
                    if units == "imperial":
                        vol_oz = e["amount_ml"] / 29.5735
                        qty_str += f" ({vol_oz:.0f} oz)"
                    else:
                        qty_str += f" ({e['amount_ml']:.0f} mL)"

                food_table.add_row(
                    e.get("id", "?"),
                    Text(cat.capitalize(), style=cat_style),
                    e.get("name", "—"),
                    qty_str,
                    str(int(e.get("calories", 0))),
                    str(e.get("protein_g", 0)),
                    str(e.get("carbs_g", 0)),
                    str(e.get("fat_g", 0)),
                )

        # Totals footer
        food_table.add_section()
        food_table.add_row(
            "", "",
            Text("Total", style="bold"),
            "",
            Text(str(int(totals["calories"])), style="bold"),
            Text(str(totals["protein_g"]), style="bold"),
            Text(str(totals["carbs_g"]),   style="bold"),
            Text(str(totals["fat_g"]),     style="bold"),
        )

    console.print(food_table)

    # Hydration summary inline beneath the table
    water_ml = totals["water_ml"]
    drink_entries = [e for e in food_entries if e.get("meal_category") == "drink"]
    if units == "imperial":
        water_display = f"{water_ml / 29.5735:.0f} oz"
    else:
        water_display = f"{water_ml:.0f} mL"

    if drink_entries:
        n = len(drink_entries)
        cprint(
            f"  [blue]Hydration[/blue]  {water_display}  "
            f"[dim]({n} drink{'s' if n != 1 else ''})[/dim]"
        )
    else:
        cprint(f"  [dim]Hydration  {water_display}  (no drinks logged)[/dim]")


def _render_custom_foods_table(foods: List[Dict[str, Any]]) -> None:
    console = get_console()
    table = Table(
        title="Custom Foods",
        show_lines=False,
    )
    table.add_column("#",          style="dim", width=4)
    table.add_column("Name",       min_width=20, max_width=28)
    table.add_column("Type",       width=6)
    table.add_column("Qty / Unit", justify="right", width=12)
    table.add_column("kcal",       justify="right", width=6)
    table.add_column("P",          justify="right", width=5)
    table.add_column("C",          justify="right", width=5)
    table.add_column("F",          justify="right", width=5)

    for i, f in enumerate(foods, start=1):
        kind = "[blue]drink[/blue]" if f.get("is_drink") else "food"
        table.add_row(
            str(i),
            f.get("name", "—"),
            kind,
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

def _manage_custom_foods_menu(units: str) -> None:
    while True:
        clear_console()
        foods = _load_custom_foods()

        if foods:
            _render_custom_foods_table(foods)
        else:
            cprint("[dim]No custom foods defined yet.[/dim]\n")

        cprint("\n[bold purple]Manage Custom Foods[/bold purple]")
        cprint("[dim]Select an option:[/dim]\n")
        cprint("  [cyan]1[/cyan]) Add a custom food or drink")
        if foods:
            cprint("  [cyan]2[/cyan]) Edit a custom food")
            cprint("  [cyan]3[/cyan]) Delete a custom food")
        cprint("  [cyan]b[/cyan]) Back")

        choice = cinput("\nChoice: ").strip().lower()

        if choice == "1":
            _add_custom_food(foods, units)
        elif choice == "2" and foods:
            _edit_custom_food(foods, units)
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
    is_drink_default: bool = False,
    volume_ml_default: Optional[float] = None,
    units: str = "imperial",
) -> Optional[Dict[str, Any]]:
    name = _prompt_str("Name: ", default=name_default)
    if not name:
        return None

    quantity = _prompt_float("Quantity (e.g. 1.5): ", min_=0.01, default=quantity_default)
    unit = _prompt_str("Unit (e.g. cup, g, oz, serving): ", default=unit_default)
    calories = _prompt_float("Calories: ", min_=0.0, default=calories_default)
    protein_g = _prompt_float("Protein (g): ", min_=0.0, default=protein_default)
    carbs_g = _prompt_float("Carbs (g): ", min_=0.0, default=carbs_default)
    fat_g = _prompt_float("Fat (g): ", min_=0.0, default=fat_default)

    is_drink_str = _prompt_choice(
        "Is this a drink? (yes/no): ",
        choices=("yes", "no"),
        default="yes" if is_drink_default else "no",
    )
    is_drink = is_drink_str == "yes"

    volume_ml: Optional[float] = None
    if is_drink:
        if units == "imperial":
            vol_oz = _prompt_float(
                "Volume per serving (oz): ",
                min_=0.0,
                default=round(volume_ml_default / 29.5735, 1) if volume_ml_default else None,
            )
            volume_ml = vol_oz * 29.5735
        else:
            volume_ml = _prompt_float(
                "Volume per serving (mL): ",
                min_=0.0,
                default=volume_ml_default,
            )

    return dict(
        name=name,
        calories=calories,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        unit=unit,
        quantity=quantity,
        is_drink=is_drink,
        volume_ml_per_unit=volume_ml,
    )


def _add_custom_food(foods: List[Dict[str, Any]], units: str) -> None:
    clear_console()
    cprint("[bold]Add Custom Food or Drink[/bold]\n")
    fields = _prompt_food_fields(units=units)
    if fields is None:
        return
    food = _make_custom_food(**fields)
    foods.append(food)
    _save_custom_foods(foods)
    cprint(f"[green]✔ '{food['name']}' saved.[/green]")
    cinput("\nPress Enter to continue.")


def _edit_custom_food(foods: List[Dict[str, Any]], units: str) -> None:
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
        is_drink_default=existing.get("is_drink", False),
        volume_ml_default=existing.get("volume_ml_per_unit"),
        units=units,
    )
    if fields is None:
        return

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
# Logging actions
# ---------------------------------------------------------------------------

_SOURCE_STYLE = {
    "foundation": "green",
    "sr_legacy":  "cyan",
    "branded":    "yellow",
}
_SOURCE_LABEL = {
    "foundation": "Foundation",
    "sr_legacy":  "SR Legacy",
    "branded":    "Branded",
}


def _render_search_results(results: List[Dict[str, Any]], units: str) -> None:
    """Print a compact numbered table of FDC search results."""
    console = get_console()
    table = Table(show_lines=False, show_header=True, header_style="bold")
    table.add_column("#",       style="dim",  width=3,  no_wrap=True)
    table.add_column("Source",               width=10, no_wrap=True)
    table.add_column("Item",    min_width=24, max_width=36)
    table.add_column("kcal",    justify="right", width=6,  no_wrap=True)
    table.add_column("Serving", justify="right", width=16, no_wrap=True)

    for i, r in enumerate(results, start=1):
        source = r.get("source", "")
        style  = _SOURCE_STYLE.get(source, "white")
        label  = _SOURCE_LABEL.get(source, source.capitalize())

        kcal_100 = r.get("kcal_per_100g")
        s_grams  = r.get("serving_grams")
        s_label  = r.get("serving_label") or ""

        # Show kcal for the default serving if we can, else per 100g
        if kcal_100 is not None and s_grams:
            kcal_serving = kcal_100 * s_grams / 100.0
            kcal_str = str(int(kcal_serving))
        elif kcal_100 is not None:
            kcal_str = f"{int(kcal_100)}/100g"
        else:
            kcal_str = "—"

        # Serving display
        if s_label and s_grams:
            serving_str = f"{s_label} ({s_grams:.0f}g)"
        elif s_label:
            serving_str = s_label
        elif s_grams:
            serving_str = f"{s_grams:.0f}g"
        else:
            serving_str = "100g"

        table.add_row(
            str(i),
            Text(label, style=style),
            r.get("description", "—"),
            kcal_str,
            serving_str,
        )

    console.print(table)


def _log_entry(d: date, units: str) -> None:
    """Search-first entry point for logging food or drink."""
    db_available = db_stats(FDC_DB_PATH) is not None

    while True:
        clear_console()
        cprint("[bold]Log Food or Drink[/bold]\n")

        if db_available:
            cprint("[dim]Type to search the food database, or:[/dim]")
            cprint("  [dim](c)[/dim] choose from custom foods")
            cprint("  [dim](m)[/dim] enter manually")
            cprint("  [dim](b)[/dim] cancel\n")
            query = cinput("Search: ").strip()
        else:
            cprint("[dim](c)[/dim] choose from custom foods")
            cprint("[dim](m)[/dim] enter manually")
            cprint("[dim](b)[/dim] cancel\n")
            query = cinput("Choice: ").strip().lower()

        if query.lower() == "b":
            return
        if query.lower() == "m":
            _log_manually(d, units)
            return
        if query.lower() == "c":
            _log_from_custom(d, units)
            return

        if not query:
            continue

        # Run the search
        results = search_foods(FDC_DB_PATH, query, limit=_FDC_SEARCH_LIMIT)

        clear_console()
        cprint(f"[bold]Results for:[/bold] [cyan]{query}[/cyan]\n")

        if not results:
            cprint("[yellow]No results found.[/yellow]")
            cprint("[dim]Try different keywords, or:[/dim]")
        else:
            _render_search_results(results, units)

        cprint("")
        if results:
            cprint("[dim]Enter a number to log that item, or:[/dim]")
        cprint("  [dim](r)[/dim] refine search")
        cprint("  [dim](c)[/dim] choose from custom foods")
        cprint("  [dim](m)[/dim] enter manually" +
               (f" [dim](pre-filled as '{query}')[/dim]" if not results else ""))
        cprint("  [dim](b)[/dim] cancel\n")

        pick = cinput("Choice: ").strip().lower()

        if pick == "b":
            return
        if pick == "r":
            continue  # loop back to search prompt
        if pick == "m":
            _log_manually(d, units, name_prefill=query if not results else "")
            return
        if pick == "c":
            _log_from_custom(d, units)
            return

        if results and pick.isdigit():
            idx = int(pick) - 1
            if 0 <= idx < len(results):
                _log_from_fdc(d, results[idx], units)
                return
            else:
                cprint("[yellow]Number out of range.[/yellow]")
                cinput("Press Enter to try again.")
                continue

        cprint("[yellow]Invalid choice.[/yellow]")
        cinput("Press Enter to try again.")


def _log_from_fdc(d: date, food: Dict[str, Any], units: str) -> None:
    """Confirm quantity and log a food record sourced from the FDC database."""
    clear_console()

    kcal_100  = food.get("kcal_per_100g")  or 0.0
    prot_100  = food.get("protein_per_100g") or 0.0
    carb_100  = food.get("carbs_per_100g")  or 0.0
    fat_100   = food.get("fat_per_100g")    or 0.0
    s_grams   = food.get("serving_grams")
    s_label   = food.get("serving_label") or "serving"
    name      = food["description"]

    # Default quantity in servings (1 serving = s_grams g)
    default_servings = 1.0
    if s_grams:
        kcal_serving = kcal_100 * s_grams / 100.0
        cprint(f"[bold]{name}[/bold]")
        cprint(f"[dim]Default serving: {s_label} ({s_grams:.0f}g) = {int(kcal_serving)} kcal[/dim]\n")
    else:
        # No serving size known — work in 100g units
        s_grams = 100.0
        s_label = "100g"
        cprint(f"[bold]{name}[/bold]")
        cprint(f"[dim]No serving size on record — quantities in 100g units[/dim]\n")

    meal_category = _prompt_choice(
        f"Category ({'/'.join(MEAL_CATEGORIES)}): ",
        choices=MEAL_CATEGORIES,
        default="uncategorized",
    )

    servings = _prompt_float(
        f"Servings [{s_label}]: ",
        min_=0.01,
        default=default_servings,
    )

    total_grams = s_grams * servings
    scale       = total_grams / 100.0

    calories  = kcal_100 * scale
    protein_g = prot_100 * scale
    carbs_g   = carb_100 * scale
    fat_g     = fat_100  * scale

    amount_ml: Optional[float] = None
    if meal_category == "drink":
        if units == "imperial":
            oz = _prompt_float("Volume (oz, 0 to skip): ", min_=0.0, default=0.0)
            amount_ml = oz * 29.5735 if oz > 0 else None
        else:
            ml = _prompt_float("Volume (mL, 0 to skip): ", min_=0.0, default=0.0)
            amount_ml = ml if ml > 0 else None

    entry = make_food_entry(
        name=name,
        calories=calories,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        quantity=servings,
        unit=s_label,
        meal_category=meal_category,
        amount_ml=amount_ml,
    )
    append_entry(d, "food_entries", entry)
    cprint(f"[green]✔ Logged {name} ({int(calories)} kcal)[/green]")
    cinput("\nPress Enter to continue.")


def _log_from_custom(d: date, units: str) -> None:
    """Quick-pick from saved custom foods."""
    custom_foods = _load_custom_foods()
    if not custom_foods:
        cprint("[yellow]No custom foods saved yet.[/yellow]")
        cinput("\nPress Enter to continue.")
        return

    clear_console()
    _render_custom_foods_table(custom_foods)
    cprint("\n[dim]Enter a number to log, or blank to cancel.[/dim]")
    raw = cinput("Selection: ").strip()
    if not raw:
        return
    try:
        idx = int(raw) - 1
        if not (0 <= idx < len(custom_foods)):
            raise ValueError
    except ValueError:
        cprint("[yellow]Invalid selection.[/yellow]")
        cinput("\nPress Enter to continue.")
        return

    _log_from_template(d, custom_foods[idx], units)


def _log_manually(d: date, units: str, name_prefill: str = "") -> None:
    name = _prompt_str("Name: ", default=name_prefill)
    if not name:
        return

    meal_category = _prompt_choice(
        f"Category ({'/'.join(MEAL_CATEGORIES)}): ",
        choices=MEAL_CATEGORIES,
        default="uncategorized",
    )

    quantity = _prompt_float("Quantity (e.g. 1.5): ", min_=0.01, default=1.0)
    unit = _prompt_str("Unit (e.g. cup, g, oz, serving): ", default="serving")
    calories = _prompt_float("Calories: ", min_=0.0, default=0.0)
    protein_g = _prompt_float("Protein (g): ", min_=0.0, default=0.0)
    carbs_g = _prompt_float("Carbs (g): ", min_=0.0, default=0.0)
    fat_g = _prompt_float("Fat (g): ", min_=0.0, default=0.0)

    amount_ml: Optional[float] = None
    if meal_category == "drink":
        if units == "imperial":
            oz = _prompt_float("Volume (oz, 0 to skip): ", min_=0.0, default=0.0)
            amount_ml = oz * 29.5735 if oz > 0 else None
        else:
            ml = _prompt_float("Volume (mL, 0 to skip): ", min_=0.0, default=0.0)
            amount_ml = ml if ml > 0 else None

    entry = make_food_entry(
        name=name,
        calories=calories,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        quantity=quantity,
        unit=unit,
        meal_category=meal_category,
        amount_ml=amount_ml,
    )
    append_entry(d, "food_entries", entry)
    cprint(f"[green]✔ Logged {name} ({int(calories)} kcal)[/green]")
    cinput("\nPress Enter to continue.")


def _log_from_template(d: date, template: Dict[str, Any], units: str) -> None:
    is_drink = template.get("is_drink", False)
    cprint(
        f"\n[bold]{template['name']}[/bold]  "
        f"[dim]{int(template['calories'])} kcal / "
        f"{template['quantity']} {template['unit']}[/dim]\n"
    )

    default_cat = "drink" if is_drink else "uncategorized"
    meal_category = _prompt_choice(
        f"Category ({'/'.join(MEAL_CATEGORIES)}): ",
        choices=MEAL_CATEGORIES,
        default=default_cat,
    )

    base_qty = template.get("quantity", 1.0)
    quantity = _prompt_float(
        f"Quantity [{template['unit']}] (default {base_qty}): ",
        min_=0.01,
        default=base_qty,
    )

    scale = quantity / base_qty if base_qty else 1.0
    calories  = template.get("calories",  0.0) * scale
    protein_g = template.get("protein_g", 0.0) * scale
    carbs_g   = template.get("carbs_g",   0.0) * scale
    fat_g     = template.get("fat_g",     0.0) * scale

    amount_ml: Optional[float] = None
    vol_per_unit = template.get("volume_ml_per_unit")
    if is_drink and vol_per_unit:
        amount_ml = vol_per_unit * scale

    entry = make_food_entry(
        name=template["name"],
        calories=calories,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        quantity=quantity,
        unit=template.get("unit", "serving"),
        meal_category=meal_category,
        amount_ml=amount_ml,
    )
    append_entry(d, "food_entries", entry)
    cprint(f"[green]✔ Logged {template['name']} ({int(calories)} kcal)[/green]")
    cinput("\nPress Enter to continue.")


def _delete_food(d: date) -> None:
    clear_console()
    day = load_day(d)
    entries = day.get("food_entries", [])

    if not entries:
        cprint("[yellow]No entries to delete.[/yellow]")
        cinput("\nPress Enter to continue.")
        return

    cprint("[bold]Delete Entry[/bold]\n")
    for e in entries:
        cat = e.get("meal_category", "")
        cat_style = _CATEGORY_STYLE.get(cat, "dim")
        cprint(
            f"  [cyan]{e['id']}[/cyan]  "
            f"[{cat_style}]{cat.capitalize()}[/{cat_style}]  "
            f"{e['name']} — {int(e.get('calories', 0))} kcal"
        )

    entry_id = cinput("\nEnter ID to delete (or blank to cancel): ").strip()
    if not entry_id:
        return

    removed = delete_entry(d, "food_entries", entry_id)
    if removed:
        cprint("[green]✔ Entry deleted.[/green]")
    else:
        cprint("[yellow]No entry found with that ID.[/yellow]")
    cinput("\nPress Enter to continue.")