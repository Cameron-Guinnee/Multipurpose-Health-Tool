from __future__ import annotations

import os
import platform


_rich_available = None


def get_console():
    """Return a fresh Console instance each call so terminal width is always current.

    Rich's Console caches terminal width at construction time. By not caching
    the instance here, every render picks up the actual current window size —
    so resizing and pressing Enter always produces a correctly-sized redraw.
    """
    global _rich_available

    if _rich_available is False:
        return None

    try:
        from rich.console import Console
        _rich_available = True
        return Console()
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