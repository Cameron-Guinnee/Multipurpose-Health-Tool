# interface/menu_settings.py
from core.console_manager import cprint,cinput,clear_console
from core.data_manager import Environment

def run_settings_menu(env: Environment) -> None:
    clear_console()
    cprint("[bold]Settings[/bold]\n")

    units = str(env.config.get("units", "imperial")).lower()
    cprint(f"Current units: [cyan]{units}[/cyan]")
    cprint("\n(Stub) You’ll eventually edit settings here.")
    cprint("\nPress Enter to return.")
    cinput("")