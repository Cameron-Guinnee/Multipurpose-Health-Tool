from interface.menu_main import run_main_menu
from interface.menu_settings import run_settings_menu

MENUS = { 
    "main_menu": run_main_menu,
    "settings_menu": run_settings_menu
}

def get_menu(menu_name: str): 
    return MENUS.get(menu_name)
    