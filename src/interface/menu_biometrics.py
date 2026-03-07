from core.console_manager import cprint,cinput,clear_console
from core.data_manager import Environment

def run_biometrics_menu(env: Environment) -> None:
    clear_console()
    cprint("[bold]Biometrics[/bold]")
    cprint("[dim]Coming soon: BP, weight, height, waist, and more.[/dim]")
    cprint("\nPress Enter to return.")
    cinput("")