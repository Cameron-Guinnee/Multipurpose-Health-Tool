import sys 
from core import data_manager 
from core.console_manager import cprint,cinput,clear_console


def main():
    clear_console()
    cprint("[purple][=== INITIALIZATION ===][/purple]")
    environment = data_manager.ensure_environment()
    
    
    
if __name__ == "__main__":
    try: 
        main()
    except KeyboardInterrupt: 
        cprint("\n[yellow][!] Interrupted by user. Exiting gracefully. (from main.py)[/yellow]")
        sys.exit(0) 
    except Exception as e: 
        cprint(f"\n[red][!] Fatal error: {e} (from main.py)[/red]")
        sys.exit(1)

