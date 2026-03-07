# src/interface/menu_main.py
from __future__ import annotations

from typing import List

from core.dashboard_manager import render_main_dashboard 
from core.console_manager import cprint, cinput, clear_console
from core.data_manager import Environment

from core.menu_manager import get_menu
from interface.common import MenuItem 


def run_main_menu(env: Environment) -> None:
    FOOD_DIARY_MENU = "food_diary_menu"
    BIOMETRICS_MENU = "biometrics_menu"
    SETTINGS_MENU = "settings_menu"

    """Main entry menu. Keeps orchestration here, delegates features to actions."""
    items: List[MenuItem] = [
        MenuItem("1", "Food Diary (calories & nutrition)", get_menu(FOOD_DIARY_MENU)),
        MenuItem("2", "Biometrics (BP, weight, measurements)", get_menu(BIOMETRICS_MENU)),
        MenuItem("3", "Settings", get_menu(SETTINGS_MENU)),
        MenuItem("q", "Quit", _quit),
    ]

    while True:
        clear_console()
        render_main_dashboard(env)
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


def _quit(env: Environment) -> None:
    raise SystemExit(0)