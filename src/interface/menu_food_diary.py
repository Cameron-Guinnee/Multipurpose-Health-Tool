from core.console_manager import cprint,cinput,clear_console
from core.data_manager import Environment

def run_food_diary_menu(env: Environment) -> None:
    clear_console()
    cprint("[bold]Food Diary[/bold]")
    cprint("[dim]Coming soon: log foods, calories, macros, micronutrients.[/dim]")
    cprint("\nPress Enter to return.")
    cinput("")