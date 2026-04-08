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
from interface.common import MenuItem,build_menu_panel,run_menu_action 

def run_main_menu(env: Environment) -> None: 
    FOOD_DIARY_MENU = "food_diary_menu" 
    BIOMETRICS_MENU = "biometrics_menu" 
    SETTINGS_MENU = "settings_menu" 
    
    items = [ 
        MenuItem("1", "Food Diary (calories & nutrition)", get_menu(FOOD_DIARY_MENU)), 
        MenuItem("2", "Biometrics (BP, weight, measurements)", get_menu(BIOMETRICS_MENU)), 
        MenuItem("3", "Settings", get_menu(SETTINGS_MENU)), 
        MenuItem("q", "Quit", _quit)
    ]
    
    while True: 
        clear_console() 
        env.reload()
        render_main_dashboard(env) 
        cprint(build_menu_panel("Main Menu", items)) 
        choice = cinput("[magenta]Choice[/magenta]: ").strip().lower() 
        
        if not run_menu_action(items, choice, env): 
            cprint("[yellow]Invalid choice. Press Enter to try again.[/yellow]") 
  
def _quit(env: Environment) -> None:
    clear_console()
    raise SystemExit(0)