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
    CUSTOM_RECIPES_PATH,
    CUSTOM_MEALS_PATH,
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
from interface.common import MenuItem,build_menu_panel,run_menu_action 

FDC_DB_PATH = DATA_DIR / "fdc" / "fdc.db"
_FDC_SEARCH_LIMIT = 15

MEAL_CATEGORIES = ("breakfast", "lunch", "dinner", "snack", "drink", "uncategorized")

_CATEGORY_STYLE: Dict[str, str] = {
    "breakfast":     "yellow",
    "lunch":         "green",
    "dinner":        "cyan",
    "snack":         "magenta",
    "drink":         "blue",
    "uncategorized": "dim",
}

_CATEGORY_ORDER = ["breakfast", "lunch", "dinner", "snack", "drink", "uncategorized"]

_SOURCE_STYLE = {"foundation": "green", "sr_legacy": "cyan", "branded": "yellow"}
_SOURCE_LABEL = {"foundation": "Foundation", "sr_legacy": "SR Legacy", "branded": "Branded"}


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _load_collection(path, key: str) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        result = data.get(key, [])
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_collection(path, key: str, items: List[Dict[str, Any]]) -> None:
    _atomic_write_json(path, {key: items})


def _load_custom_foods()    -> List[Dict[str, Any]]: return _load_collection(CUSTOM_FOODS_PATH,   "foods")
def _save_custom_foods(v)   -> None: _save_collection(CUSTOM_FOODS_PATH,   "foods",   v)
def _load_custom_recipes()  -> List[Dict[str, Any]]: return _load_collection(CUSTOM_RECIPES_PATH, "recipes")
def _save_custom_recipes(v) -> None: _save_collection(CUSTOM_RECIPES_PATH, "recipes", v)
def _load_custom_meals()    -> List[Dict[str, Any]]: return _load_collection(CUSTOM_MEALS_PATH,   "meals")
def _save_custom_meals(v)   -> None: _save_collection(CUSTOM_MEALS_PATH,   "meals",   v)


# ---------------------------------------------------------------------------
# Constructors
# ---------------------------------------------------------------------------

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
        "id":        uuid.uuid4().hex[:8],
        "name":      name.strip(),
        "calories":  round(calories,  1),
        "protein_g": round(protein_g, 1),
        "carbs_g":   round(carbs_g,   1),
        "fat_g":     round(fat_g,     1),
        "unit":      unit.strip(),
        "quantity":  quantity,
        "is_drink":  is_drink,
    }
    if is_drink and volume_ml_per_unit is not None:
        entry["volume_ml_per_unit"] = round(volume_ml_per_unit, 1)
    return entry


def _sum_ingredients(ingredients: List[Dict[str, Any]]) -> Dict[str, float]:
    return {
        "calories":  round(sum(i.get("calories",  0) for i in ingredients), 1),
        "protein_g": round(sum(i.get("protein_g", 0) for i in ingredients), 1),
        "carbs_g":   round(sum(i.get("carbs_g",   0) for i in ingredients), 1),
        "fat_g":     round(sum(i.get("fat_g",     0) for i in ingredients), 1),
    }


def _make_custom_recipe(
    name: str,
    ingredients: List[Dict[str, Any]],
    servings: float = 1.0,
    unit: str = "serving",
) -> Dict[str, Any]:
    """A recipe is a named food item whose nutrition is the sum of its ingredients."""
    return {
        "id":          uuid.uuid4().hex[:8],
        "name":        name.strip(),
        "servings":    servings,
        "unit":        unit.strip(),
        "ingredients": ingredients,
        **_sum_ingredients(ingredients),
    }


def _make_custom_meal(name: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """A meal is a named group of food items logged together."""
    return {
        "id":    uuid.uuid4().hex[:8],
        "name":  name.strip(),
        "items": items,
    }


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
    
        is_today = (viewed_date == today)
        _render_food_diary_nav(is_today) 
    
        items = [ 
            MenuItem("1", "Create an entry", lambda _: _log_entry(viewed_date, units)),
            MenuItem("2", "Delete an entry", lambda _: _delete_food(viewed_date)), 
            MenuItem("3", "Manage custom foods", lambda _: _manage_custom_foods_menu(units)),
            MenuItem("4", "Manage recipes", lambda _: _manage_custom_recipes_menu(units)), 
            MenuItem("5", "Manage meals", lambda _: _manage_custom_meals_menu(units)), 
            MenuItem("b", "Back", lambda _: None)
        ]
    
        cprint("") 
        cprint(build_menu_panel("Food diary", items, note="Select an option.")) 
    
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
            cprint("[yellow]Invalid choice. Press enter to try again.[/yellow]") 
            cinput("") 
   
# ---------------------------------------------------------------------------
# Date navigation
# ---------------------------------------------------------------------------

def _prompt_date(today: date) -> Optional[date]:
    """Accepts YYYY-MM-DD, MM-DD, or MM/DD. Rejects future dates."""
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

def _render_food_diary(d: date, units: str) -> None:
    console = get_console()
    day    = load_day(d)
    totals = get_daily_totals(d)

    food_entries = day.get("food_entries", [])
    grouped: Dict[str, List[Dict[str, Any]]] = {cat: [] for cat in _CATEGORY_ORDER}
    for e in food_entries:
        cat = e.get("meal_category", "uncategorized")
        grouped[cat if cat in grouped else "uncategorized"].append(e)

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
        show_lines=False, show_header=True, header_style="bold", title_justify="left",
    )
    food_table.add_column("ID",   style="dim", width=6,  no_wrap=True)
    food_table.add_column("Meal", width=11, no_wrap=True)
    food_table.add_column("Item", min_width=20, max_width=32)
    food_table.add_column("Qty",  justify="right", width=12, no_wrap=True)
    food_table.add_column("kcal", justify="right", width=6,  no_wrap=True)
    food_table.add_column("P(g)", justify="right", width=5,  no_wrap=True)
    food_table.add_column("C(g)", justify="right", width=5,  no_wrap=True)
    food_table.add_column("F(g)", justify="right", width=5,  no_wrap=True)

    if not any(grouped[cat] for cat in _CATEGORY_ORDER):
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
                    vol = e["amount_ml"]
                    qty_str += f" ({vol / 29.5735:.0f} oz)" if units == "imperial" else f" ({vol:.0f} mL)"

                food_table.add_row(
                    e.get("id", "?"),
                    Text(cat.capitalize(), style=cat_style),
                    e.get("name", "—"),
                    qty_str,
                    str(int(e.get("calories", 0))),
                    str(e.get("protein_g", 0)),
                    str(e.get("carbs_g",   0)),
                    str(e.get("fat_g",     0)),
                )

        food_table.add_section()
        food_table.add_row(
            "", "", Text("Total", style="bold"), "",
            Text(str(int(totals["calories"])), style="bold"),
            Text(str(totals["protein_g"]),     style="bold"),
            Text(str(totals["carbs_g"]),        style="bold"),
            Text(str(totals["fat_g"]),          style="bold"),
        )

    console.print(food_table)

    water_ml      = totals["water_ml"]
    drink_entries = [e for e in food_entries if e.get("meal_category") == "drink"]
    water_display = f"{water_ml / 29.5735:.0f} oz" if units == "imperial" else f"{water_ml:.0f} mL"
    if drink_entries:
        n = len(drink_entries)
        cprint(f"  [blue]Hydration[/blue]  {water_display}  [dim]({n} drink{'s' if n != 1 else ''})[/dim]")
    else:
        cprint(f"  [dim]Hydration  {water_display}  (no drinks logged)[/dim]")

def _render_food_diary_nav(is_today: bool) -> None: 
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

def _render_custom_foods_table(foods: List[Dict[str, Any]]) -> None:
    console = get_console()
    table = Table(title="Custom Foods", show_lines=False)
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
            str(i), f.get("name", "—"), kind,
            f"{f.get('quantity', 1):.1f} {f.get('unit', '')}",
            str(int(f.get("calories", 0))),
            str(f.get("protein_g", 0)),
            str(f.get("carbs_g",   0)),
            str(f.get("fat_g",     0)),
        )
    console.print(table)


def _render_custom_recipes_table(recipes: List[Dict[str, Any]]) -> None:
    console = get_console()
    table = Table(title="Custom Recipes", show_lines=False)
    table.add_column("#",           style="dim", width=4)
    table.add_column("Name",        min_width=20, max_width=28)
    table.add_column("Ingredients", justify="right", width=12)
    table.add_column("Servings",    justify="right", width=10)
    table.add_column("kcal",        justify="right", width=6)
    table.add_column("P",           justify="right", width=5)
    table.add_column("C",           justify="right", width=5)
    table.add_column("F",           justify="right", width=5)

    for i, r in enumerate(recipes, start=1):
        table.add_row(
            str(i), r.get("name", "—"),
            str(len(r.get("ingredients", []))),
            f"{r.get('servings', 1):.1f} {r.get('unit', '')}",
            str(int(r.get("calories", 0))),
            str(r.get("protein_g", 0)),
            str(r.get("carbs_g",   0)),
            str(r.get("fat_g",     0)),
        )
    console.print(table)


def _render_custom_meals_table(meals: List[Dict[str, Any]]) -> None:
    console = get_console()
    table = Table(title="Custom Meals", show_lines=False)
    table.add_column("#",     style="dim", width=4)
    table.add_column("Name", min_width=20, max_width=28)
    table.add_column("Items", justify="right", width=8)
    table.add_column("kcal",  justify="right", width=6)
    table.add_column("P",     justify="right", width=5)
    table.add_column("C",     justify="right", width=5)
    table.add_column("F",     justify="right", width=5)

    for i, m in enumerate(meals, start=1):
        totals = _sum_ingredients(m.get("items", []))
        table.add_row(
            str(i), m.get("name", "—"),
            str(len(m.get("items", []))),
            str(int(totals["calories"])),
            str(totals["protein_g"]),
            str(totals["carbs_g"]),
            str(totals["fat_g"]),
        )
    console.print(table)


def _render_search_results(results: List[Dict[str, Any]]) -> None:
    console = get_console()
    table = Table(show_lines=False, show_header=True, header_style="bold")
    table.add_column("#",       style="dim",  width=3,  no_wrap=True)
    table.add_column("Source",               width=10, no_wrap=True)
    table.add_column("Item",    min_width=24, max_width=36)
    table.add_column("kcal",    justify="right", width=6,  no_wrap=True)
    table.add_column("Serving", justify="right", width=16, no_wrap=True)

    for i, r in enumerate(results, start=1):
        source   = r.get("source", "")
        kcal_100 = r.get("kcal_per_100g")
        s_grams  = r.get("serving_grams")
        s_label  = r.get("serving_label") or ""

        if kcal_100 is not None and s_grams:
            kcal_str = str(int(kcal_100 * s_grams / 100.0))
        elif kcal_100 is not None:
            kcal_str = f"{int(kcal_100)}/100g"
        else:
            kcal_str = "—"

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
            Text(_SOURCE_LABEL.get(source, source.capitalize()), style=_SOURCE_STYLE.get(source, "white")),
            r.get("description", "—"),
            kcal_str, serving_str,
        )
    console.print(table)


# ---------------------------------------------------------------------------
# Custom foods management
# ---------------------------------------------------------------------------
def _manage_custom_foods_menu(units: str) -> None: 
    while True: 
        clear_console() 
        foods = _load_custom_foods() 
        
        if foods: 
            _render_custom_foods_table(foods)
        else: 
            # TODO: Render an empty table when no custom foods are defined, as is done for the food diary itself when no foods are logged 
            cprint("[dim] No custom foods defined yet.[/dim]\n") 
        
        items = [ 
            MenuItem("1", "Add a custom food/drink", lambda _: _add_custom_food(foods, units)),
            MenuItem("2", "Edit a custom food/drink", lambda _: _edit_custom_food(foods, units), enabled=bool(foods)),
            MenuItem("3", "Delete a custom food/drink", lambda _: _delete_custom_food(foods), enabled=bool(foods)), 
            MenuItem("b", "Back", lambda _: None),
        ]
        
        cprint("") 
        cprint(build_menu_panel("Manage Custom Foods", items, note="Select an option.")) 
        
        choice = cinput("\n[bold magenta]Choice[/bold magenta]: ").strip().lower() 
        
        if choice == "b": 
            return 
        
        if not run_menu_action(items, choice, None): 
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

    quantity  = _prompt_float("Quantity (e.g. 1.5): ", min_=0.01, default=quantity_default)
    unit      = _prompt_str("Unit (e.g. cup, g, oz, serving): ", default=unit_default)
    calories  = _prompt_float("Calories: ",    min_=0.0, default=calories_default)
    protein_g = _prompt_float("Protein (g): ", min_=0.0, default=protein_default)
    carbs_g   = _prompt_float("Carbs (g): ",   min_=0.0, default=carbs_default)
    fat_g     = _prompt_float("Fat (g): ",     min_=0.0, default=fat_default)

    is_drink = _prompt_choice(
        "Is this a drink? (yes/no): ", choices=("yes", "no"),
        default="yes" if is_drink_default else "no",
    ) == "yes"

    volume_ml: Optional[float] = None
    if is_drink:
        if units == "imperial":
            vol_oz = _prompt_float(
                "Volume per serving (oz): ", min_=0.0,
                default=round(volume_ml_default / 29.5735, 1) if volume_ml_default else None,
            )
            volume_ml = vol_oz * 29.5735
        else:
            volume_ml = _prompt_float("Volume per serving (mL): ", min_=0.0, default=volume_ml_default)

    return dict(
        name=name, calories=calories, protein_g=protein_g, carbs_g=carbs_g, fat_g=fat_g,
        unit=unit, quantity=quantity, is_drink=is_drink, volume_ml_per_unit=volume_ml,
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
    idx = _prompt_list_index(foods, "edit")
    if idx is None:
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
    idx = _prompt_list_index(foods, "delete")
    if idx is None:
        return
    removed = foods.pop(idx)
    _save_custom_foods(foods)
    cprint(f"[green]✔ '{removed['name']}' deleted.[/green]")
    cinput("\nPress Enter to continue.")


# ---------------------------------------------------------------------------
# Ingredient picker  (shared by recipes and meals)
# ---------------------------------------------------------------------------

def _pick_ingredient(units: str) -> Optional[Dict[str, Any]]:
    """Prompt the user to pick one ingredient from the FDC database, custom
    foods, or manual entry. Returns a normalised ingredient dict or None."""
    db_available = db_stats(FDC_DB_PATH) is not None

    while True:
        clear_console()
        cprint("[bold]Add Ingredient[/bold]\n")

        if db_available:
            cprint("[dim]Type to search the food database, or:[/dim]")
            cprint("  [dim](c)[/dim] choose from custom foods")
            cprint("  [dim](m)[/dim] enter manually")
            cprint("  [dim](b)[/dim] cancel\n")
            query = cinput("Search: ").strip()
        else:
            cprint("  [dim](c)[/dim] choose from custom foods")
            cprint("  [dim](m)[/dim] enter manually")
            cprint("  [dim](b)[/dim] cancel\n")
            query = cinput("Choice: ").strip().lower()

        ql = query.lower()
        if ql == "b":
            return None
        if ql == "m":
            return _pick_ingredient_manually()
        if ql == "c":
            return _pick_ingredient_from_custom()
        if not query:
            continue

        # FDC search
        results = search_foods(FDC_DB_PATH, query, limit=_FDC_SEARCH_LIMIT)
        clear_console()
        cprint(f"[bold]Results for:[/bold] [cyan]{query}[/cyan]\n")

        if not results:
            cprint("[yellow]No results found.[/yellow]")
            cprint("[dim]Try different keywords, or:[/dim]")
        else:
            _render_search_results(results)

        cprint("")
        if results:
            cprint("[dim]Enter a number to use that item, or:[/dim]")
        cprint("  [dim](r)[/dim] refine search")
        cprint("  [dim](c)[/dim] choose from custom foods")
        cprint("  [dim](m)[/dim] enter manually")
        cprint("  [dim](b)[/dim] cancel\n")

        pick = cinput("Choice: ").strip().lower()

        if pick == "b":
            return None
        if pick == "r":
            continue
        if pick == "m":
            return _pick_ingredient_manually(name_prefill=query if not results else "")
        if pick == "c":
            return _pick_ingredient_from_custom()
        if results and pick.isdigit():
            idx = int(pick) - 1
            if 0 <= idx < len(results):
                return _ingredient_from_fdc(results[idx])
            cprint("[yellow]Number out of range.[/yellow]")
            cinput("Press Enter to try again.")
            continue

        cprint("[yellow]Invalid choice.[/yellow]")
        cinput("Press Enter to try again.")


def _ingredient_from_fdc(food: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Ask for a serving quantity and return a normalised ingredient dict."""
    kcal_100 = food.get("kcal_per_100g")   or 0.0
    prot_100 = food.get("protein_per_100g") or 0.0
    carb_100 = food.get("carbs_per_100g")   or 0.0
    fat_100  = food.get("fat_per_100g")     or 0.0
    s_grams  = food.get("serving_grams")
    s_label  = food.get("serving_label") or "serving"
    name     = food["description"]

    if s_grams:
        cprint(f"\n[bold]{name}[/bold]  "
               f"[dim]({s_label}, {s_grams:.0f}g = {int(kcal_100 * s_grams / 100)} kcal)[/dim]")
    else:
        s_grams = 100.0
        s_label = "100g"
        cprint(f"\n[bold]{name}[/bold]  [dim](no serving size — using 100g)[/dim]")

    servings = _prompt_float(f"Servings [{s_label}]: ", min_=0.01, default=1.0)
    scale    = s_grams * servings / 100.0

    return {
        "name":      name,
        "calories":  round(kcal_100 * scale, 1),
        "protein_g": round(prot_100 * scale, 1),
        "carbs_g":   round(carb_100 * scale, 1),
        "fat_g":     round(fat_100  * scale, 1),
        "quantity":  servings,
        "unit":      s_label,
    }


def _pick_ingredient_from_custom() -> Optional[Dict[str, Any]]:
    foods = _load_custom_foods()
    if not foods:
        cprint("[yellow]No custom foods saved yet.[/yellow]")
        cinput("\nPress Enter to continue.")
        return None

    clear_console()
    _render_custom_foods_table(foods)
    idx = _prompt_list_index(foods, "select")
    if idx is None:
        return None

    f     = foods[idx]
    base  = f.get("quantity", 1.0)
    qty   = _prompt_float(f"Quantity [{f.get('unit', 'serving')}]: ", min_=0.01, default=base)
    scale = qty / base if base else 1.0

    return {
        "name":      f["name"],
        "calories":  round(f.get("calories",  0) * scale, 1),
        "protein_g": round(f.get("protein_g", 0) * scale, 1),
        "carbs_g":   round(f.get("carbs_g",   0) * scale, 1),
        "fat_g":     round(f.get("fat_g",     0) * scale, 1),
        "quantity":  qty,
        "unit":      f.get("unit", "serving"),
    }


def _pick_ingredient_manually(name_prefill: str = "") -> Optional[Dict[str, Any]]:
    name = _prompt_str("Name: ", default=name_prefill)
    if not name:
        return None
    quantity  = _prompt_float("Quantity: ",    min_=0.01, default=1.0)
    unit      = _prompt_str("Unit: ",          default="serving")
    calories  = _prompt_float("Calories: ",    min_=0.0,  default=0.0)
    protein_g = _prompt_float("Protein (g): ", min_=0.0,  default=0.0)
    carbs_g   = _prompt_float("Carbs (g): ",   min_=0.0,  default=0.0)
    fat_g     = _prompt_float("Fat (g): ",     min_=0.0,  default=0.0)
    return dict(name=name, calories=calories, protein_g=protein_g,
                carbs_g=carbs_g, fat_g=fat_g, quantity=quantity, unit=unit)


def _build_ingredient_list(units: str, existing: Optional[List[Dict]] = None) -> List[Dict[str, Any]]:
    """Interactive loop to add/remove ingredients. Returns the confirmed list,
    or an empty list if the user cancels before confirming."""
    items: List[Dict[str, Any]] = list(existing or [])

    while True:
        clear_console()
        cprint("[bold]Ingredients[/bold]\n")
        if items:
            for i, ing in enumerate(items, start=1):
                cprint(
                    f"  [dim]{i}.[/dim] {ing['name']}  "
                    f"[dim]{ing.get('quantity', 1):.1f} {ing.get('unit', '')} — "
                    f"{int(ing.get('calories', 0))} kcal[/dim]"
                )
            t = _sum_ingredients(items)
            cprint(
                f"\n  [bold]Total:[/bold] {int(t['calories'])} kcal  "
                f"P {t['protein_g']}g  C {t['carbs_g']}g  F {t['fat_g']}g"
            )
        else:
            cprint("  [dim](none yet)[/dim]")

        cprint("\n  [cyan]a[/cyan]) Add ingredient")
        if items:
            cprint("  [cyan]r[/cyan]) Remove an ingredient")
            cprint("  [cyan]d[/cyan]) Done")
        cprint("  [cyan]b[/cyan]) Cancel / discard\n")

        choice = cinput("Choice: ").strip().lower()

        if choice == "a":
            ing = _pick_ingredient(units)
            if ing:
                items.append(ing)
        elif choice == "r" and items:
            idx = _prompt_list_index(items, "remove")
            if idx is not None:
                removed = items.pop(idx)
                cprint(f"[green]✔ Removed '{removed['name']}'.[/green]")
                cinput("Press Enter to continue.")
        elif choice == "d" and items:
            return items
        elif choice == "b":
            return []
        # "d" with no items falls through and loops again


# ---------------------------------------------------------------------------
# Recipes management
# ---------------------------------------------------------------------------
def _manage_custom_recipes_menu(units: str) -> None: 
    while True: 
        clear_console() 
        recipes = _load_custom_recipes() 
        
        if recipes: 
            _render_custom_recipes_table(recipes) 
        else: 
            # TODO: Render an empty table when no custom recipes are defined, as is done for the food diary itself when no foods are logged 
            cprint("[dim]No custom recipes defined yet.[/dim]\n")
        
        items = [ 
            MenuItem("1", "Add a recipe", lambda _: _add_custom_recipe(units)), 
            MenuItem("2", "Edit a recipe", lambda _: _edit_custom_recipe(recipes, units), enabled=bool(recipes)),
            MenuItem("3", "Delete a recipe", lambda _: _delete_custom_recipe(recipes), enabled=bool(recipes)), 
            MenuItem("b", "Back", lambda _: None),
        ]
        
        cprint("")
        cprint(build_menu_panel("Manage Recipes", items, note="A recipe is a single food item built from summed ingredients.",)) 
        
        choice = cinput("\n[bold magenta]Choice[/bold magenta]: ").strip().lower() 
        
        if choice == "b": 
            return 
            
        if not run_menu_action(items, choice, None): 
            cprint("[yellow]Invalid choice. Press Enter to try again.[/yellow]") 
            cinput("") 


def _add_custom_recipe(units: str) -> None:
    clear_console()
    cprint("[bold]Add Recipe[/bold]\n")
    name = _prompt_str("Recipe name: ")
    if not name:
        return

    ingredients = _build_ingredient_list(units)
    if not ingredients:
        return

    servings = _prompt_float("Total servings this recipe makes: ", min_=0.01, default=1.0)
    unit     = _prompt_str("Serving unit (e.g. serving, slice): ", default="serving")

    recipe = _make_custom_recipe(name, ingredients, servings=servings, unit=unit)
    recipes = _load_custom_recipes()
    recipes.append(recipe)
    _save_custom_recipes(recipes)
    cprint(f"[green]✔ Recipe '{recipe['name']}' saved ({int(recipe['calories'])} kcal total).[/green]")
    cinput("\nPress Enter to continue.")


def _edit_custom_recipe(recipes: List[Dict[str, Any]], units: str) -> None:
    clear_console()
    _render_custom_recipes_table(recipes)
    cprint("\n[bold]Edit Recipe[/bold]")
    idx = _prompt_list_index(recipes, "edit")
    if idx is None:
        return

    existing = recipes[idx]
    cprint(f"\n[dim]Editing '{existing['name']}' — press Enter to keep current value.[/dim]\n")

    name = _prompt_str("Recipe name: ", default=existing.get("name", ""))
    if not name:
        return

    ingredients = _build_ingredient_list(units, existing=existing.get("ingredients", []))
    if not ingredients:
        return

    servings = _prompt_float("Total servings: ", min_=0.01, default=existing.get("servings", 1.0))
    unit     = _prompt_str("Serving unit: ", default=existing.get("unit", "serving"))

    updated = _make_custom_recipe(name, ingredients, servings=servings, unit=unit)
    updated["id"] = existing["id"]
    recipes[idx] = updated
    _save_custom_recipes(recipes)
    cprint(f"[green]✔ Recipe '{updated['name']}' updated.[/green]")
    cinput("\nPress Enter to continue.")


def _delete_custom_recipe(recipes: List[Dict[str, Any]]) -> None:
    clear_console()
    _render_custom_recipes_table(recipes)
    cprint("\n[bold]Delete Recipe[/bold]")
    idx = _prompt_list_index(recipes, "delete")
    if idx is None:
        return
    removed = recipes.pop(idx)
    _save_custom_recipes(recipes)
    cprint(f"[green]✔ Recipe '{removed['name']}' deleted.[/green]")
    cinput("\nPress Enter to continue.")


# ---------------------------------------------------------------------------
# Meals management
# ---------------------------------------------------------------------------
def _manage_custom_meals_menu(units: str) -> None: 
    while True: 
        clear_console() 
        meals = _load_custom_meals() 
        
        if meals: 
            _render_custom_meals_table(meals) 
        else: 
            # TODO: Render an empty table when no custom meals are defined, as is done for the food diary itself when no food items are logged
            cprint("[dim]No custom meals defined yet.[/dim]\n")
        
        items = [ 
            MenuItem("1", "Add a meal", lambda _: _add_custom_meal(units)), 
            MenuItem("2", "Edit a meal", lambda _: _edit_custom_meal(meals, units), enabled=bool(meals)),
            MenuItem("3", "Delete a meal", lambda _: _delete_custom_meal(meals), enabled=bool(meals)), 
            MenuItem("b", "Back", lambda _: None),
        ]
        
        cprint("") 
        cprint(build_menu_panel("Manage Meals", items, note="A meal is a group of items logged together as separate entries."))
        
        choice = cinput("\n[bold magenta]Choice[/bold magenta]: ").strip().lower() 
        
        if choice == "b": 
            return 
        
        if not run_menu_action(items, choice, None): 
            cprint("[yellow]Invalid choice. Press Enter to try again.[/yellow]") 
            cinput("") 
            


def _add_custom_meal(units: str) -> None:
    clear_console()
    cprint("[bold]Add Meal[/bold]\n")
    name = _prompt_str("Meal name (e.g. Burger & Fries): ")
    if not name:
        return

    items = _build_ingredient_list(units)
    if not items:
        return

    meal  = _make_custom_meal(name, items)
    meals = _load_custom_meals()
    meals.append(meal)
    _save_custom_meals(meals)
    totals = _sum_ingredients(items)
    cprint(f"[green]✔ Meal '{meal['name']}' saved ({int(totals['calories'])} kcal).[/green]")
    cinput("\nPress Enter to continue.")


def _edit_custom_meal(meals: List[Dict[str, Any]], units: str) -> None:
    clear_console()
    _render_custom_meals_table(meals)
    cprint("\n[bold]Edit Meal[/bold]")
    idx = _prompt_list_index(meals, "edit")
    if idx is None:
        return

    existing = meals[idx]
    cprint(f"\n[dim]Editing '{existing['name']}' — press Enter to keep current value.[/dim]\n")

    name = _prompt_str("Meal name: ", default=existing.get("name", ""))
    if not name:
        return

    items = _build_ingredient_list(units, existing=existing.get("items", []))
    if not items:
        return

    updated = _make_custom_meal(name, items)
    updated["id"] = existing["id"]
    meals[idx] = updated
    _save_custom_meals(meals)
    cprint(f"[green]✔ Meal '{updated['name']}' updated.[/green]")
    cinput("\nPress Enter to continue.")


def _delete_custom_meal(meals: List[Dict[str, Any]]) -> None:
    clear_console()
    _render_custom_meals_table(meals)
    cprint("\n[bold]Delete Meal[/bold]")
    idx = _prompt_list_index(meals, "delete")
    if idx is None:
        return
    removed = meals.pop(idx)
    _save_custom_meals(meals)
    cprint(f"[green]✔ Meal '{removed['name']}' deleted.[/green]")
    cinput("\nPress Enter to continue.")


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _log_entry(d: date, units: str) -> None:
    """Search-first entry point for logging food, drink, a recipe, or a meal."""
    db_available = db_stats(FDC_DB_PATH) is not None

    while True:
        clear_console()
        cprint("[bold]Log Food or Drink[/bold]\n")

        if db_available:
            cprint("[dim]Type to search the food database, or:[/dim]")
            cprint("  [dim](c)[/dim] choose from custom foods")
            cprint("  [dim](r)[/dim] log a saved recipe")
            cprint("  [dim](ml)[/dim] log a saved meal")
            cprint("  [dim](m)[/dim] enter manually")
            cprint("  [dim](b)[/dim] cancel\n")
            query = cinput("Search: ").strip()
        else:
            cprint("  [dim](c)[/dim] choose from custom foods")
            cprint("  [dim](r)[/dim] log a saved recipe")
            cprint("  [dim](ml)[/dim] log a saved meal")
            cprint("  [dim](m)[/dim] enter manually")
            cprint("  [dim](b)[/dim] cancel\n")
            query = cinput("Choice: ").strip().lower()

        ql = query.lower()
        if ql == "b":   return
        if ql == "m":   _log_manually(d, units);          return
        if ql == "c":   _log_from_custom(d, units);       return
        if ql == "r":   _log_from_recipe(d, units);       return
        if ql == "ml":  _log_from_meal(d, units);         return
        if not query:   continue

        results = search_foods(FDC_DB_PATH, query, limit=_FDC_SEARCH_LIMIT)
        clear_console()
        cprint(f"[bold]Results for:[/bold] [cyan]{query}[/cyan]\n")

        if not results:
            cprint("[yellow]No results found.[/yellow]")
            cprint("[dim]Try different keywords, or:[/dim]")
        else:
            _render_search_results(results)

        cprint("")
        if results:
            cprint("[dim]Enter a number to log that item, or:[/dim]")
        cprint("  [dim](r)[/dim] refine search")
        cprint("  [dim](c)[/dim] choose from custom foods")
        cprint("  [dim](m)[/dim] enter manually" +
               (f" [dim](pre-filled as '{query}')[/dim]" if not results else ""))
        cprint("  [dim](b)[/dim] cancel\n")

        pick = cinput("Choice: ").strip().lower()

        if pick == "b": return
        if pick == "r": continue
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
            cprint("[yellow]Number out of range.[/yellow]")
            cinput("Press Enter to try again.")
            continue

        cprint("[yellow]Invalid choice.[/yellow]")
        cinput("Press Enter to try again.")


def _log_from_fdc(d: date, food: Dict[str, Any], units: str) -> None:
    clear_console()

    kcal_100 = food.get("kcal_per_100g")   or 0.0
    prot_100 = food.get("protein_per_100g") or 0.0
    carb_100 = food.get("carbs_per_100g")   or 0.0
    fat_100  = food.get("fat_per_100g")     or 0.0
    s_grams  = food.get("serving_grams")
    s_label  = food.get("serving_label") or "serving"
    name     = food["description"]

    if s_grams:
        cprint(f"[bold]{name}[/bold]")
        cprint(f"[dim]Default serving: {s_label} ({s_grams:.0f}g) = {int(kcal_100 * s_grams / 100)} kcal[/dim]\n")
    else:
        s_grams = 100.0
        s_label = "100g"
        cprint(f"[bold]{name}[/bold]")
        cprint(f"[dim]No serving size on record — quantities in 100g units[/dim]\n")

    meal_category = _prompt_choice(
        f"Category ({'/'.join(MEAL_CATEGORIES)}): ", choices=MEAL_CATEGORIES, default="uncategorized",
    )
    servings  = _prompt_float(f"Servings [{s_label}]: ", min_=0.01, default=1.0)
    scale     = s_grams * servings / 100.0
    amount_ml = _prompt_drink_volume(meal_category, units)

    entry = make_food_entry(
        name=name,
        calories=kcal_100 * scale, protein_g=prot_100 * scale,
        carbs_g=carb_100 * scale,  fat_g=fat_100 * scale,
        quantity=servings, unit=s_label,
        meal_category=meal_category, amount_ml=amount_ml,
    )
    append_entry(d, "food_entries", entry)
    cprint(f"[green]✔ Logged {name} ({int(kcal_100 * scale)} kcal)[/green]")
    cinput("\nPress Enter to continue.")


def _log_from_custom(d: date, units: str) -> None:
    custom_foods = _load_custom_foods()
    if not custom_foods:
        cprint("[yellow]No custom foods saved yet.[/yellow]")
        cinput("\nPress Enter to continue.")
        return

    clear_console()
    _render_custom_foods_table(custom_foods)
    cprint("\n[dim]Enter a number to log, or blank to cancel.[/dim]")
    idx = _prompt_list_index(custom_foods, "log")
    if idx is None:
        return
    _log_from_template(d, custom_foods[idx], units)


def _log_from_recipe(d: date, units: str) -> None:
    """Log a saved recipe as a single diary entry (summed macros)."""
    recipes = _load_custom_recipes()
    if not recipes:
        cprint("[yellow]No custom recipes saved yet.[/yellow]")
        cinput("\nPress Enter to continue.")
        return

    clear_console()
    _render_custom_recipes_table(recipes)
    cprint("\n[dim]Enter a number to log, or blank to cancel.[/dim]")
    idx = _prompt_list_index(recipes, "log")
    if idx is None:
        return

    recipe        = recipes[idx]
    base_servings = recipe.get("servings", 1.0)
    cprint(
        f"\n[bold]{recipe['name']}[/bold]  "
        f"[dim]{int(recipe.get('calories', 0))} kcal / "
        f"{base_servings} {recipe.get('unit', 'serving')}[/dim]\n"
    )

    meal_category = _prompt_choice(
        f"Category ({'/'.join(MEAL_CATEGORIES)}): ", choices=MEAL_CATEGORIES, default="uncategorized",
    )
    servings = _prompt_float(f"Servings [{recipe.get('unit', 'serving')}]: ", min_=0.01, default=1.0)
    scale    = servings / base_servings if base_servings else 1.0

    entry = make_food_entry(
        name=recipe["name"],
        calories=recipe.get("calories",  0) * scale,
        protein_g=recipe.get("protein_g", 0) * scale,
        carbs_g=recipe.get("carbs_g",    0) * scale,
        fat_g=recipe.get("fat_g",        0) * scale,
        quantity=servings, unit=recipe.get("unit", "serving"),
        meal_category=meal_category,
    )
    append_entry(d, "food_entries", entry)
    cprint(f"[green]✔ Logged {recipe['name']} ({int(recipe.get('calories', 0) * scale)} kcal)[/green]")
    cinput("\nPress Enter to continue.")


def _log_from_meal(d: date, units: str) -> None:
    """Log a saved meal — each item becomes its own diary entry."""
    meals = _load_custom_meals()
    if not meals:
        cprint("[yellow]No custom meals saved yet.[/yellow]")
        cinput("\nPress Enter to continue.")
        return

    clear_console()
    _render_custom_meals_table(meals)
    cprint("\n[dim]Enter a number to log, or blank to cancel.[/dim]")
    idx = _prompt_list_index(meals, "log")
    if idx is None:
        return

    meal          = meals[idx]
    meal_category = _prompt_choice(
        f"Category ({'/'.join(MEAL_CATEGORIES)}): ", choices=MEAL_CATEGORIES, default="uncategorized",
    )

    total_kcal = 0.0
    for item in meal.get("items", []):
        entry = make_food_entry(
            name=item["name"],
            calories=item.get("calories",  0),
            protein_g=item.get("protein_g", 0),
            carbs_g=item.get("carbs_g",    0),
            fat_g=item.get("fat_g",        0),
            quantity=item.get("quantity", 1),
            unit=item.get("unit", "serving"),
            meal_category=meal_category,
        )
        append_entry(d, "food_entries", entry)
        total_kcal += item.get("calories", 0)

    n = len(meal.get("items", []))
    cprint(f"[green]✔ Logged meal '{meal['name']}' ({n} items, {int(total_kcal)} kcal total)[/green]")
    cinput("\nPress Enter to continue.")


def _log_manually(d: date, units: str, name_prefill: str = "") -> None:
    name = _prompt_str("Name: ", default=name_prefill)
    if not name:
        return

    meal_category = _prompt_choice(
        f"Category ({'/'.join(MEAL_CATEGORIES)}): ", choices=MEAL_CATEGORIES, default="uncategorized",
    )
    quantity  = _prompt_float("Quantity (e.g. 1.5): ", min_=0.01, default=1.0)
    unit      = _prompt_str("Unit (e.g. cup, g, oz, serving): ", default="serving")
    calories  = _prompt_float("Calories: ",    min_=0.0, default=0.0)
    protein_g = _prompt_float("Protein (g): ", min_=0.0, default=0.0)
    carbs_g   = _prompt_float("Carbs (g): ",   min_=0.0, default=0.0)
    fat_g     = _prompt_float("Fat (g): ",     min_=0.0, default=0.0)
    amount_ml = _prompt_drink_volume(meal_category, units)

    entry = make_food_entry(
        name=name, calories=calories, protein_g=protein_g, carbs_g=carbs_g, fat_g=fat_g,
        quantity=quantity, unit=unit, meal_category=meal_category, amount_ml=amount_ml,
    )
    append_entry(d, "food_entries", entry)
    cprint(f"[green]✔ Logged {name} ({int(calories)} kcal)[/green]")
    cinput("\nPress Enter to continue.")


def _log_from_template(d: date, template: Dict[str, Any], units: str) -> None:
    is_drink = template.get("is_drink", False)
    base_qty = template.get("quantity", 1.0)
    cprint(
        f"\n[bold]{template['name']}[/bold]  "
        f"[dim]{int(template['calories'])} kcal / {base_qty} {template['unit']}[/dim]\n"
    )

    meal_category = _prompt_choice(
        f"Category ({'/'.join(MEAL_CATEGORIES)}): ", choices=MEAL_CATEGORIES,
        default="drink" if is_drink else "uncategorized",
    )
    quantity = _prompt_float(
        f"Quantity [{template['unit']}] (default {base_qty}): ", min_=0.01, default=base_qty,
    )
    scale = quantity / base_qty if base_qty else 1.0

    amount_ml: Optional[float] = None
    vol_per_unit = template.get("volume_ml_per_unit")
    if is_drink and vol_per_unit:
        amount_ml = vol_per_unit * scale

    entry = make_food_entry(
        name=template["name"],
        calories=template.get("calories",  0) * scale,
        protein_g=template.get("protein_g", 0) * scale,
        carbs_g=template.get("carbs_g",    0) * scale,
        fat_g=template.get("fat_g",        0) * scale,
        quantity=quantity, unit=template.get("unit", "serving"),
        meal_category=meal_category, amount_ml=amount_ml,
    )
    append_entry(d, "food_entries", entry)
    cprint(f"[green]✔ Logged {template['name']} ({int(template.get('calories', 0) * scale)} kcal)[/green]")
    cinput("\nPress Enter to continue.")


def _delete_food(d: date) -> None:
    clear_console()
    day     = load_day(d)
    entries = day.get("food_entries", [])

    if not entries:
        cprint("[yellow]No entries to delete.[/yellow]")
        cinput("\nPress Enter to continue.")
        return

    cprint("[bold]Delete Entry[/bold]\n")
    for e in entries:
        cat       = e.get("meal_category", "")
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


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

def _prompt_list_index(items: List[Any], action: str = "select") -> Optional[int]:
    """Prompt for a 1-based index; return 0-based int or None on cancel/error."""
    raw = cinput(f"\nEnter number to {action} (or blank to cancel): ").strip()
    if not raw:
        return None
    try:
        idx = int(raw) - 1
        if not (0 <= idx < len(items)):
            raise ValueError
        return idx
    except ValueError:
        cprint("[yellow]Invalid selection.[/yellow]")
        cinput("\nPress Enter to continue.")
        return None


def _prompt_drink_volume(meal_category: str, units: str) -> Optional[float]:
    """Return volume in mL if category is 'drink' and the user provides a value."""
    if meal_category != "drink":
        return None
    if units == "imperial":
        oz = _prompt_float("Volume (oz, 0 to skip): ", min_=0.0, default=0.0)
        return oz * 29.5735 if oz > 0 else None
    else:
        ml = _prompt_float("Volume (mL, 0 to skip): ", min_=0.0, default=0.0)
        return ml if ml > 0 else None
