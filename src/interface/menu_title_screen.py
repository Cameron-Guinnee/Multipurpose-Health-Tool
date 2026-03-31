"""
Health Tool - Title Screen
Requires: pip install rich

Usage:
    from title_screen import title_screen
    title_screen()
    # ... your main menu here
"""

import os
import sys
import time
import threading

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.live import Live
from rich.style import Style
from rich import box

console = Console()

# ── Palette ────────────────────────────────────────────────────────────────────
TEAL     = "#00C9A7"
TEAL_DIM = "#007A66"
MINT     = "#A8FFDA"
GOLD     = "#FFD166"
WHITE    = "#F0F4F8"
DARK     = "#0D1B2A"
GREY     = "#4A5568"

# ── ASCII logo ─────────────────────────────────────────────────────────────────
LOGO_LINES = [
    "██╗  ██╗███████╗ █████╗ ██╗  ████████╗██╗  ██╗",
    "██║  ██║██╔════╝██╔══██╗██║  ╚══██╔══╝██║  ██║",
    "███████║█████╗  ███████║██║     ██║   ███████║",
    "██╔══██║██╔══╝  ██╔══██║██║     ██║   ██╔══██║",
    "██║  ██║███████╗██║  ██║███████╗██║   ██║  ██║",
    "╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝╚═╝   ╚═╝  ╚═╝",
    "",
    "  ████████╗ ██████╗  ██████╗ ██╗     ███████╗  ",
    "  ╚══██╔══╝██╔═══██╗██╔═══██╗██║     ██╔════╝  ",
    "     ██║   ██║   ██║██║   ██║██║     ███████╗  ",
    "     ██║   ██║   ██║██║   ██║██║     ╚════██║  ",
    "     ██║   ╚██████╔╝╚██████╔╝███████╗███████║  ",
    "     ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝╚══════╝  ",
]

GRAD = [TEAL, MINT, TEAL, MINT, TEAL]


def _gradient_logo() -> Text:
    text = Text(justify="center")
    for line in LOGO_LINES:
        if not line.strip():
            text.append("\n")
            continue
        seg = max(1, len(line) // len(GRAD))
        for i, ch in enumerate(line):
            colour = GRAD[min(i // seg, len(GRAD) - 1)]
            text.append(ch, style=Style(color=colour, bold=True))
        text.append("\n")
    return text


def _pulse_prompt(tick: int) -> Text:
    phases = [
        (WHITE, "◆"),
        (TEAL,  "◆"),
        (MINT,  "◆"),
        (TEAL,  "◆"),
    ]
    colour, gem = phases[tick % len(phases)]
    t = Text(justify="center")
    t.append(f"  {gem}  ", style=Style(color=colour, bold=True))
    t.append("Press any key to begin  ", style=Style(color=colour, bold=True, italic=True))
    t.append(f"  {gem}", style=Style(color=colour, bold=True))
    return t


def _build_panel(tick: int) -> Panel:
    badges = ["  🫀 Heart  ", "  🧠 Mind  ", "  💪 Body  ", "  😴 Sleep  ", "  🥗 Nutrition  "]
    active = tick % len(badges)

    body = Text(justify="center")
    body.append("\n")
    body.append("╔════════════════════════════════════════════╗\n", style=Style(color=TEAL_DIM))
    body.append("║", style=Style(color=TEAL_DIM))
    body.append(" Your AIO companion for better living       ", style=Style(color=GOLD, italic=True))
    body.append("║\n", style=Style(color=TEAL_DIM))
    body.append("╚════════════════════════════════════════════╝\n", style=Style(color=TEAL_DIM))
    body.append("\n")

    for i, b in enumerate(badges):
        if i == active:
            body.append(b, style=Style(color=DARK, bgcolor=TEAL, bold=True))
        else:
            body.append(b, style=Style(color=GREY))
    body.append("\n\n")

    body.append("  v1.0.0  ", style=Style(color=GREY))
    body.append("│", style=Style(color=TEAL_DIM))
    body.append("  Built with love using Python & Rich  ", style=Style(color=GREY, italic=True))
    body.append("\n\n")
    body.append_text(_pulse_prompt(tick))
    body.append("\n")

    combined = Text(justify="center")
    combined.append_text(_gradient_logo())
    combined.append("\n")
    combined.append_text(body)

    return Panel(
        Align.center(combined, vertical="middle"),
        box=box.DOUBLE_EDGE,
        style=Style(color=TEAL, bgcolor=DARK),
        padding=(1, 4),
        title=Text("  HEALTH TOOLS  ", style=Style(color=GOLD, bold=True)),
        subtitle=Text(" © 2026 ", style=Style(color=GREY)),
    )


def run_title_screen() -> None:
    """Display the animated title screen and block until the user presses any key."""
    key_pressed = threading.Event()

    def _wait_for_key():
        if sys.platform == "win32":
            import msvcrt
            msvcrt.getch()
        else:
            import tty, termios
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                os.read(fd, 1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
        key_pressed.set()

    threading.Thread(target=_wait_for_key, daemon=True).start()

    tick = 0
    with Live(
        _build_panel(tick),
        console=console,
        screen=True,
        refresh_per_second=4,
    ) as live:
        while not key_pressed.is_set():
            tick += 1
            live.update(_build_panel(tick))
            time.sleep(0.25)

    console.clear()


if __name__ == "__main__":
    try:
        run_title_screen()
    except KeyboardInterrupt:
        pass
