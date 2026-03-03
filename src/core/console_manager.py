from __future__ import annotations 

import os 
import platform


_console = None 
_rich_available = None 


def get_console(): 
    global _console,_rich_available 
    
    if _rich_available is False: 
        return None 
    if _console is not None: 
        return _console
        
    try:
        from rich.console import Console 
        _console = Console() 
        _rich_available = True 
        return _console 
    except ModuleNotFoundError: 
        _rich_available = False 
        return None
        
def clear_console(): 
    if platform.system() == "Windows":
        os.system("cls") 
    else: 
        os.system("clear") 
        
def cprint(*args, **kwargs):
    """Console-aware print (Rich if available, else stdlib)."""
    console = get_console() 
    if console:
        console.print(*args, **kwargs) 
    else: 
        print(*args)

def cinput(text: str) -> str: 
    """Console-aware input (Rich if available, else stdlib)."""
    console = get_console() 
    if console:
        return console.input(text) 
    else: 
        return input(text)
        

     