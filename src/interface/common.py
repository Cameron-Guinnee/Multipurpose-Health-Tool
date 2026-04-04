from collections.abc import Iterable,Sequence 
from dataclasses import dataclass 
from typing import Any,Callable 

from rich.panel import Panel 
from rich.table import Table 
from rich.text import Text 
from rich.console import Group
from rich import box 


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



    