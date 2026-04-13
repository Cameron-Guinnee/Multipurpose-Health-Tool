# interface/shared.py
from __future__ import annotations

from core.console_manager import cprint,cinput 
from core.data_manager import _parse_birthdate 

from collections.abc import Iterable,Sequence 
from dataclasses import dataclass 
from typing import Any,Callable 

from datetime import date, datetime # datetime needed for dateutil default
from dateutil import parser as dateutil_parser

from rich.panel import Panel 
from rich.table import Table 
from rich.text import Text 
from rich.console import Group
from rich import box 


# ── Menu primitives ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class MenuItem:
    key: str
    label: str
    action: Callable[[Any], None]
    enabled: bool = True
    hint: str | None = None 
    
    def run(self, ctx: Any) -> None: 
        if self.enabled: 
            self.action(ctx) 
            
            
def build_menu_panel(title: str, items: Sequence[MenuItem], note: str | None = None, border_style: str = "magenta") -> Panel:
    table = Table.grid(padding=(0, 2), expand=True) 
    table.add_column(width=5, no_wrap=True) 
    table.add_column(ratio=1) 
    
    for item in items: 
        key_style = "bold cyan" if item.enabled else "dim" 
        label_style = "white" if item.enabled else "dim" 
        
        key_text = Text.assemble( 
            ("[", "bright_black"), 
            (item.key, key_style), 
            ("]", "bright_black"), 
        )
        
        label_text = Text(item.label, style=label_style) 
        if item.hint: 
            label_text.append(f"  {item.hint}", style="dim") 
        
        table.add_row(key_text, label_text) 
    
    body = [table] 
    if note: 
        body.extend([Text(""), Text(note, style="dim")]) 
    
    return Panel(
        Group(*body), 
        title=f"[bold white]{title}[/bold white]", 
        border_style=border_style, 
        box=box.ROUNDED, 
        padding=(0,1),
    )

def find_menu_item(items: Iterable[MenuItem], choice: str) -> MenuItem | None: 
    choice = choice.strip().lower() 
    return next((item for item in items if item.key.lower() == choice), None)

def run_menu_action(items: Iterable[MenuItem], choice: str, ctx: Any) -> bool: 
    item = find_menu_item(items, choice) 
    if item is None or not item.enabled: 
        return False 
    item.run(ctx) 
    return True 


# ── Prompt helpers ─────────────────────────────────────────────────────────
def prompt_units(default: str = "imperial") -> str:
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


def prompt_birthdate(prompt: str, default: str = "") -> str:
    while True:
        s = cinput(prompt).strip()
        if not s and default:
            s = default.strip()
        dt = _parse_birthdate(s)
        if dt is None:
            cprint("[yellow]Enter a valid date in YYYY-MM-DD (not in the future).[/yellow]")
            continue
        return s


def prompt_str(prompt: str, default: str = "") -> str:
    display = f"{prompt}(default {default}) " if default else prompt
    s = cinput(display).strip()
    return s if s else default


def prompt_float(prompt: str, *, min_: float = 0.0, default: float | None = None) -> float:
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


def prompt_choice(prompt: str, *, choices: tuple, default: str) -> str:
    choices_set = {c.lower() for c in choices}
    while True:
        s = cinput(f"{prompt}(default {default}) ").strip().lower()
        if not s:
            return default.lower()
        if s in choices_set:
            return s
        cprint(f"[yellow]Choose one of: {', '.join(choices)}[/yellow]")
        

def prompt_date(today: date, allow_future: bool = False) -> Optional[date]: 
    cprint("\n[dim]Enter a date (blank to cancel)[/dim]") 
    raw = cinput("Date: ").strip() 
    
    if not raw: 
        return None 
    try: 
        parsed = dateutil_parser.parse(raw, default=datetime(today.year, 1, 1)).date()
    except dateutil_parser.ParserError: 
        cprint("[yellow]Couldn't parse that date. Try something like 2025-01-05 or Jan 5.[/yellow]") 
        cinput("Press Enter to continue.") 
        return None 
    
    if not allow_future and parsed > today: 
        cprint("[yellow]Can't navigate to a future date.[/yellow]") 
        cinput("Press Enter to continue.") 
        return None 
    return parsed 
