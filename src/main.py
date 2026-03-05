import sys 
import traceback 
from core import data_manager 
from core.setup_wizard import is_setup_complete,run_setup_wizard
from core.console_manager import cprint,cinput,clear_console
from core.menu_manager import get_menu 


def main():
    clear_console()
    env = data_manager.ensure_environment()
    if not is_setup_complete(env): 
        env = run_setup_wizard(env)
    run_main_menu = get_menu("main_menu")
    run_main_menu(env) 
    
    
    
    
    
    
if __name__ == "__main__":
    try: 
        main()
    except KeyboardInterrupt: 
        cprint("\n[yellow][!] Interrupted by user. Exiting gracefully. (from main.py)[/yellow]")
        sys.exit(0) 
    except Exception as e: 
        #cprint(f"\n[red]Fatal error: {e}[/red]")
        cprint(f"[red]{traceback.format_exc()}[/red]")
        sys.exit(1)

