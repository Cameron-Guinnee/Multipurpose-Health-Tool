# src/interface/menu_main.py
from __future__ import annotations

from typing import List

from rich.panel import Panel 
from rich.table import Table 
from rich.text import Text
from rich import box 

from core.dashboard_manager import render_main_dashboard 
from core.console_manager import cprint, cinput, clear_console
from core.data_manager import Environment

from core.menu_manager import get_menu
from interface.common import MenuItem 

def _render_menu(items) -> Panel: 
    table = Table.grid(padding=(0,2)) 
    table.add_column(style="bold cyan", no_wrap=True, width=3)
    table.add_column(style="white") 
    
    for it in items: 
        key_text = Text.assemble(
            ("[", "bright_black"), 
            (it.key, "bold cyan"), 
            ("]", "bright_black"),
        )
        table.add_row(key_text, it.label)
    
    return Panel( 
        table, 
        title="[bold white]Main Menu[/bold white]", 
        border_style="magenta",
        box=box.ROUNDED,
        padding=(0,1),
    ) 
    
def run_main_menu(env: Environment) -> None:
    """Main entry menu. Keeps orchestration here, delegates features to actions."""
    FOOD_DIARY_MENU = "food_diary_menu"
    BIOMETRICS_MENU = "biometrics_menu"
    SETTINGS_MENU = "settings_menu"

    
    items: List[MenuItem] = [
        MenuItem("1", "Food Diary (calories & nutrition)", get_menu(FOOD_DIARY_MENU)),
        MenuItem("2", "Biometrics (BP, weight, measurements)", get_menu(BIOMETRICS_MENU)),
        MenuItem("3", "Settings", get_menu(SETTINGS_MENU)),
        MenuItem("q", "Quit", _quit),
    ]

    while True:
        clear_console()
        render_main_dashboard(env)
        cprint(_render_menu(items))
        choice = cinput("[magenta] Choice[/magenta]: ").strip().lower()

        match = next((it for it in items if it.key == choice), None)
        if not match:
            cprint("[yellow]Invalid choice. Press Enter to try again.[/yellow]")
            cinput("")
            continue

        match.action(env)


def _quit(env: Environment) -> None:
    clear_console()
    raise SystemExit(0)