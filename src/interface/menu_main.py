# src/interface/menu_main.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

from core.console_manager import cprint, cinput, clear_console
from core.data_manager import Environment


@dataclass(frozen=True)
class MenuItem:
    key: str
    label: str
    action: Callable[[Environment], None]


def run_main_menu(env: Environment) -> None:
    """Main entry menu. Keeps orchestration here, delegates features to actions."""
    items: List[MenuItem] = [
        MenuItem("1", "Food Diary (calories & nutrition)", _food_diary_stub),
        MenuItem("2", "Biometrics (BP, weight, measurements)", _biometrics_stub),
        MenuItem("3", "Settings", _settings_stub),
        MenuItem("q", "Quit", _quit),
    ]

    while True:
        clear_console()
        cprint("[bold purple]Multipurpose Health Tool[/bold purple]")
        cprint("[dim]Select an option:[/dim]\n")

        for it in items:
            cprint(f"  [cyan]{it.key}[/cyan]) {it.label}")

        choice = cinput("\nChoice: ").strip().lower()

        match = next((it for it in items if it.key == choice), None)
        if not match:
            cprint("[yellow]Invalid choice. Press Enter to try again.[/yellow]")
            cinput("")
            continue

        match.action(env)


# ----------------------------
# Stubs (replace these with real menus later)
# ----------------------------
def _food_diary_stub(env: Environment) -> None:
    clear_console()
    cprint("[bold]Food Diary[/bold]")
    cprint("[dim]Coming soon: log foods, calories, macros, micronutrients.[/dim]")
    cprint("\nPress Enter to return.")
    cinput("")


def _biometrics_stub(env: Environment) -> None:
    clear_console()
    cprint("[bold]Biometrics[/bold]")
    cprint("[dim]Coming soon: BP, weight, height, waist, and more.[/dim]")
    cprint("\nPress Enter to return.")
    cinput("")


def _settings_stub(env: Environment) -> None:
    clear_console()
    cprint("[bold]Settings[/bold]\n")

    units = str(env.config.get("units", "imperial")).lower()
    cprint(f"Current units: [cyan]{units}[/cyan]")
    cprint("\n(Stub) You’ll eventually edit settings here.")
    cprint("\nPress Enter to return.")
    cinput("")


def _quit(env: Environment) -> None:
    raise SystemExit(0)