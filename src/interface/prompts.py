from __future__ import annotations

from core.console_manager import cprint,cinput 
from core.data_manager import _parse_birthdate 

# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------
def _prompt_units(default: str = "imperial") -> str:
    cprint("\n[bold]Preferences[/bold]")
    cprint("Choose your measurement system:")
    cprint("  1) Imperial (lb/in/oz)")
    cprint("  2) Metric (kg/cm/ml)")
    while True:
        s = cinput(f"Selection [1/2] (default { '1' if default=='imperial' else '2' }): ").strip()
        if not s:
            return default
        if s == "1":
            return "imperial"
        if s == "2":
            return "metric"
        cprint("[yellow]Please enter 1 or 2.[/yellow]")


def _prompt_birthdate(prompt: str, default: str = "") -> str:
    while True:
        s = cinput(prompt).strip()
        if not s and default:
            s = default.strip()
        dt = _parse_birthdate(s)
        if dt is None:
            cprint("[yellow]Enter a valid date in YYYY-MM-DD (not in the future).[/yellow]")
            continue
        return s


def _prompt_str(prompt: str, default: str = "") -> str:
    display = f"{prompt}(default {default}) " if default else prompt
    s = cinput(display).strip()
    return s if s else default


def _prompt_number(prompt: str, *, min_: float = 0.0, default: float | None = None) -> float:
    default_str = f"(default {default}) " if default is not None else ""
    while True:
        s = cinput(f"{prompt}{default_str}").strip()
        if not s and default is not None:
            return float(default)
        try:
            v = float(s)
            if v < min_:
                cprint(f"[yellow]Enter a value >= {min_}.[/yellow]")
                continue
            return v
        except ValueError:
            cprint("[yellow]Please enter a number.[/yellow]")


def _prompt_choice(prompt: str, *, choices: tuple, default: str) -> str:
    choices_set = {c.lower() for c in choices}
    while True:
        s = cinput(f"{prompt}(default {default}) ").strip().lower()
        if not s:
            return default
        if s in choices_set:
            return s
        cprint(f"[yellow]Choose one of: {', '.join(choices)}[/yellow]")