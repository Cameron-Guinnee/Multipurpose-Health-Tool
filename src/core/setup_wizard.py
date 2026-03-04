from __future__ import annotations 

from dataclasses import asdict 
from datetime import datetime 
from typing import Optional,Tuple,Dict,Any 

from core.console_manager import cprint,cinput,clear_console 
from core.data_manager import (
    Environment,
    CONFIG_PATH, 
    PROFILE_PATH, 
    GOALS_PATH, 
    save_json, 
    iso_now, 
    _parse_birthdate,
    _compute_age_years, 
    _parse_positive_number,
)


def is_setup_complete(env: Environment) -> bool: 
    cfg = env.config or {} 
    if not cfg.get("setup_completed", False): 
        return False 
    
    # Minimal profile readiness 
    profile = env.profile or {} 
    required_profile = ("birthdate", "height", "weight", "activity_level") 
    if not all(str(profile.get(k, "")).strip() for k in required_profile):
        return False 
    
    # Minimal config readiness 
    units = str(cfg.get("units", "")).strip().lower() 
    if units not in {"imperial", "metric"}: 
        return False 
    
    return True 
    
def run_setup_wizard(env: Environment) -> Environment:
    """Interactive first-run wizard. Mutates env dicts and persists them."""
    cprint("[purple][=== FIRST-TIME SETUP ===][/purple]")

    # 1) Config / Preferences
    units = _prompt_units(default=_safe_units(env.config))
    env.config["units"] = units

    # optional metadata (kept internal; don't show in settings menu)
    env.config.setdefault("schema_version", 1)
    env.config.setdefault("first_run_at", iso_now())

    # 2) Profile
    _wizard_profile(env, units)

    # 3) Goals
    _wizard_goals(env, units)

    # Mark complete last (only after successful runs)
    env.config["setup_completed"] = True

    # Persist
    save_json(CONFIG_PATH, env.config)
    save_json(PROFILE_PATH, env.profile)
    save_json(GOALS_PATH, env.goals)

    cprint("[green]✔ Setup complete![/green]")
    return env
    
    
# ----------------------------
# Wizard steps
# ---------------------------- 
def _wizard_profile(env: Environment, units: str) -> None:
    cprint("\n[bold]Profile setup[/bold]")
    p = env.profile

    p["name"] = _prompt_optional("Name (optional): ", default=p.get("name", ""))

    # Keep your existing 'gender' field, but be clear about its use:
    # If you later switch to sex_for_bmr, this is where you'd do it.
    p["gender"] = _prompt_choice(
        "Gender for BMR calculation (male/female/other): ",
        choices=("male", "female", "other"),
        default=_safe_default_choice(p.get("gender"), ("male", "female", "other"), "other"),
    )

    birthdate = _prompt_birthdate("Birthdate (YYYY-MM-DD): ", default=p.get("birthdate", ""))
    p["birthdate"] = birthdate

    # NOTE: 'age' is legacy; store it only if your app still uses it.
    # Prefer computing at runtime from birthdate.
    bd = _parse_birthdate(birthdate)
    p["age"] = _compute_age_years(bd) if bd else ""

    if units == "imperial":
        p["height"] = _prompt_number("Height (inches): ", min_=1, default=p.get("height"))
        p["weight"] = _prompt_number("Weight (lb): ", min_=1, default=p.get("weight"))
    else:
        p["height"] = _prompt_number("Height (cm): ", min_=1, default=p.get("height"))
        p["weight"] = _prompt_number("Weight (kg): ", min_=1, default=p.get("weight"))

    p["activity_level"] = _prompt_choice(
        "Activity level (sedentary/light/moderate/very/extra): ",
        choices=("sedentary", "light", "moderate", "very", "extra"),
        default=_safe_default_choice(p.get("activity_level"), ("sedentary","light","moderate","very","extra"), "moderate"),
    )    

def _wizard_goals(env: Environment, units: str) -> None:
    cprint("\n[bold]Goals setup[/bold]")
    g = env.goals

    goal_type = _prompt_choice(
        "Goal type (lose/maintain/gain): ",
        choices=("lose", "maintain", "gain"),
        default=_safe_default_choice(g.get("goal_type"), ("lose","maintain","gain"), "maintain"),
    )
    g["goal_type"] = goal_type

    # Start weight default from profile weight if available
    profile_weight = env.profile.get("weight")
    if g.get("start_weight") in (None, "", 0) and profile_weight not in (None, ""):
        g["start_weight"] = profile_weight

    if goal_type == "maintain":
        # Keep goal fields clean
        g["weekly_rate"] = None
        g["target_weight"] = None
    else:
        if units == "imperial":
            g["weekly_rate"] = _prompt_number("Weekly rate (lb/week, e.g. 0.5): ", min_=0.1, default=g.get("weekly_rate"))
            g["target_weight"] = _prompt_number("Target weight (lb): ", min_=1, default=g.get("target_weight"))
        else:
            g["weekly_rate"] = _prompt_number("Weekly rate (kg/week, e.g. 0.25): ", min_=0.05, default=g.get("weekly_rate"))
            g["target_weight"] = _prompt_number("Target weight (kg): ", min_=1, default=g.get("target_weight"))

    mode = _prompt_choice(
        "Calorie target mode (auto/manual): ",
        choices=("auto", "manual"),
        default=_safe_default_choice(g.get("calorie_target_mode"), ("auto","manual"), "auto"),
    )
    g["calorie_target_mode"] = mode

    if mode == "manual":
        g["manual_calorie_target"] = int(_prompt_number("Manual calorie target (kcal/day): ", min_=1, default=g.get("manual_calorie_target")))
    else:
        g["manual_calorie_target"] = None

    # Update timestamps
    g.setdefault("created_at", iso_now())
    g["updated_at"] = iso_now()
    
# ----------------------------
# Prompt helpers
# ----------------------------

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


def _prompt_number(prompt: str, *, min_: float = 0.0, default: Any = None) -> float:
    """Prompts for a positive float with optional default."""
    default_str = ""
    if default not in (None, ""):
        default_str = f" (default {default})"
    while True:
        s = cinput(f"{prompt}{default_str} ").strip()
        if not s and default not in (None, ""):
            s = str(default)
        v = _parse_positive_number(s)
        if v is None or v < min_:
            cprint(f"[yellow]Enter a number ≥ {min_}.[/yellow]")
            continue
        return float(v)


def _prompt_choice(prompt: str, *, choices: Tuple[str, ...], default: str) -> str:
    choices_set = {c.lower() for c in choices}
    while True:
        s = cinput(f"{prompt}(default {default}) ").strip().lower()
        if not s:
            return default
        if s in choices_set:
            return s
        cprint(f"[yellow]Choose one of: {', '.join(choices)}[/yellow]")


def _prompt_optional(prompt: str, default: str = "") -> str:
    s = cinput(prompt).strip()
    return s if s else (default or "")


def _safe_units(cfg: Dict[str, Any]) -> str:
    u = str((cfg or {}).get("units", "")).strip().lower()
    return u if u in {"imperial", "metric"} else "imperial"


def _safe_default_choice(current: Any, choices: Tuple[str, ...], fallback: str) -> str:
    cur = str(current or "").strip().lower()
    return cur if cur in {c.lower() for c in choices} else fallback