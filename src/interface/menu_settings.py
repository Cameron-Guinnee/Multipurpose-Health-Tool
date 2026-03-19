# interface/menu_settings.py
from __future__ import annotations

from pathlib import Path

from core.console_manager import cprint, cinput, clear_console
from core.data_manager import Environment, DATA_DIR
from core.fdc_importer import build_database, db_stats

FDC_DB_PATH = DATA_DIR / "fdc" / "fdc.db"

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_settings_menu(env: Environment) -> None:
    while True:
        clear_console()
        cprint("[bold purple]Settings[/bold purple]\n")

        units = str(env.config.get("units", "imperial")).lower()
        cprint(f"  Units: [cyan]{units}[/cyan]")
        _print_fdc_status()

        cprint("\n[dim]Select an option:[/dim]\n")
        cprint("  [cyan]1[/cyan]) Toggle units (imperial / metric)")
        cprint("  [cyan]2[/cyan]) Food database (USDA FoodData Central)")
        cprint("  [cyan]b[/cyan]) Back")

        choice = cinput("\nChoice: ").strip().lower()

        if choice == "1":
            _toggle_units(env)
        elif choice == "2":
            _fdc_menu(env)
        elif choice == "b":
            return
        else:
            cprint("[yellow]Invalid choice.[/yellow]")
            cinput("")


# ---------------------------------------------------------------------------
# Units toggle
# ---------------------------------------------------------------------------

def _toggle_units(env: Environment) -> None:
    current = str(env.config.get("units", "imperial")).lower()
    new = "metric" if current == "imperial" else "imperial"
    env.config["units"] = new

    from core.data_manager import CONFIG_PATH, save_json
    save_json(CONFIG_PATH, env.config)
    cprint(f"[green]✔ Units changed to {new}.[/green]")
    cinput("\nPress Enter to continue.")


# ---------------------------------------------------------------------------
# FDC status helper
# ---------------------------------------------------------------------------

def _print_fdc_status() -> None:
    stats = db_stats(FDC_DB_PATH)
    if stats is None:
        cprint("  Food database: [yellow]not installed[/yellow]")
    else:
        total = stats.get("total", 0)
        parts = []
        if "foundation" in stats:
            parts.append(f"{stats['foundation']:,} foundation")
        if "sr_legacy" in stats:
            parts.append(f"{stats['sr_legacy']:,} SR legacy")
        if "branded" in stats:
            parts.append(f"{stats['branded']:,} branded")
        detail = ", ".join(parts)
        cprint(f"  Food database: [green]{total:,} foods[/green] [dim]({detail})[/dim]")


# ---------------------------------------------------------------------------
# FDC submenu
# ---------------------------------------------------------------------------

def _fdc_menu(env: Environment) -> None:
    while True:
        clear_console()
        cprint("[bold purple]Food Database (USDA FoodData Central)[/bold purple]\n")
        _print_fdc_status()

        cprint("[dim]The USDA FoodData Central database lets you search ~500,000 foods[/dim]")
        cprint("[dim]when logging instead of entering every item by hand.[/dim]")
        cprint("")
        cprint("[dim]You will need to download the JSON datasets from:[/dim]")
        cprint("[dim]  https://fdc.nal.usda.gov/download-datasets[/dim]")
        cprint("")
        cprint("[dim]Recommended downloads (JSON format):[/dim]")
        cprint("[dim]  - Foundation Foods   (~7 MB unzipped)[/dim]")
        cprint("[dim]  - SR Legacy          (~205 MB unzipped)[/dim]")
        cprint("[dim]  - Branded Foods      (~3.1 GB unzipped)[/dim]")
        cprint("")
        cprint("[dim]Place the .zip or extracted .json files anywhere on your machine,[/dim]")
        cprint("[dim]then use option 1 below to point the importer at them.[/dim]")
        cprint("")

        cprint("  [cyan]1[/cyan]) Import / rebuild database from local files")
        if db_stats(FDC_DB_PATH):
            cprint("  [cyan]2[/cyan]) Remove database")
        cprint("  [cyan]b[/cyan]) Back")

        choice = cinput("\nChoice: ").strip().lower()

        if choice == "1":
            _run_import()
        elif choice == "2" and db_stats(FDC_DB_PATH):
            _remove_db()
        elif choice == "b":
            return
        else:
            cprint("[yellow]Invalid choice.[/yellow]")
            cinput("")


# ---------------------------------------------------------------------------
# Import flow
# ---------------------------------------------------------------------------

def _run_import() -> None:
    clear_console()
    cprint("[bold]Import USDA Food Database[/bold]\n")
    cprint("[dim]Enter the paths to your downloaded FDC JSON or ZIP files.[/dim]")
    cprint("[dim]You can enter one or more files (Foundation, SR Legacy, Branded).[/dim]")
    cprint("[dim]Press Enter with a blank path when you are done.[/dim]\n")

    paths: list[Path] = []
    while True:
        raw = cinput(f"  File {len(paths) + 1} (or Enter to finish): ").strip()
        if not raw:
            if not paths:
                cprint("[yellow]No files entered. Cancelling.[/yellow]")
                cinput("\nPress Enter to continue.")
                return
            break

        # Strip surrounding quotes (common when drag-dropping on Windows)
        raw = raw.strip('"').strip("'")
        p = Path(raw)
        if not p.exists():
            cprint(f"[yellow]  File not found: {p}[/yellow]")
            continue
        if p.suffix.lower() not in (".json", ".zip"):
            cprint(f"[yellow]  Expected a .json or .zip file, got: {p.suffix}[/yellow]")
            continue
        paths.append(p)
        cprint(f"  [green]✔ Added: {p.name}[/green]")

    cprint(f"\n[dim]Ready to import {len(paths)} file(s) into {FDC_DB_PATH}[/dim]")
    cprint("[yellow]This may take several minutes for large datasets.[/yellow]")
    confirm = cinput("\nProceed? (y/n): ").strip().lower()
    if confirm != "y":
        cprint("Cancelled.")
        cinput("\nPress Enter to continue.")
        return

    cprint("")
    try:
        total = build_database(
            json_paths=paths,
            db_path=FDC_DB_PATH,
            progress_cb=lambda msg: cprint(f"  {msg}"),
        )
        cprint(f"\n[green]✔ Import complete — {total:,} foods available.[/green]")
    except Exception as e:
        cprint(f"\n[red]Import failed: {e}[/red]")
        cprint("[dim]The partial database (if any) has been removed.[/dim]")

    cinput("\nPress Enter to continue.")


def _remove_db() -> None:
    confirm = cinput("Remove the food database? This cannot be undone. (y/n): ").strip().lower()
    if confirm == "y":
        FDC_DB_PATH.unlink(missing_ok=True)
        cprint("[green]✔ Database removed.[/green]")
    else:
        cprint("Cancelled.")
    cinput("\nPress Enter to continue.")