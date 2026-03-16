from __future__ import annotations 
 
from typing import Tuple,Dict,Any 

from core.console_manager import cprint,cinput 
from core.data_manager import (
    Environment,
    CONFIG_PATH, 
    PROFILE_PATH, 
    GOALS_PATH, 
    save_json, 
    iso_now, 
    _parse_birthdate,
    _compute_age_years, 
)
from core.units import lb_to_kg,in_to_cm
from interface.prompts import _prompt_birthdate,_prompt_choice,_prompt_number,_prompt_units,_prompt_str

def is_setup_complete(env: Environment) -> bool: 
    cfg = env.config or {} 
    if not cfg.get("setup_completed", False): 
        return False 
    
    # Minimal profile readiness 
    profile = env.profile or {} 
    required_profile = ("birthdate", "sex_for_bmr", "height_cm", "weight_kg", "activity_level") 
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
    profile = env.profile

    profile["name"] = _prompt_str("Name (optional): ", default=profile.get("name", ""))

    # Keep your existing 'gender' field, but be clear about its use:
    # If you later switch to sex_for_bmr, this is where you'd do it.
    profile["sex_for_bmr"] = _prompt_choice(
        "Sex for BMR calculation (male/female): ",
        choices=("male", "female"),
        default=_safe_default_choice(profile.get("sex_for_bmr"), ("male", "female"), None),
    )

    birthdate = _prompt_birthdate("Birthdate (YYYY-MM-DD): ", default=profile.get("birthdate", ""))
    profile["birthdate"] = birthdate

    # NOTE: 'age' is legacy; store it only if your app still uses it.
    # Prefer computing at runtime from birthdate.
    bd = _parse_birthdate(birthdate)
    profile["age"] = _compute_age_years(bd) if bd else ""

    if units == "imperial":
        imperial_weight = _prompt_number("Weight (lb): ", min_=1, default=profile.get("weight_kg"))
        imperial_height = _prompt_number("Height (inches): ", min_=1, default=profile.get("height_cm")) 
        profile["weight_kg"] = lb_to_kg(imperial_weight)
        profile["height_cm"] = in_to_cm(imperial_height) 
    else:
        profile["weight_kg"] = _prompt_number("Weight (kg): ", min_=1, default=profile.get("weight_kg"))
        profile["height_cm"] = _prompt_number("Height (cm): ", min_=1, default=profile.get("height_cm"))

    profile["activity_level"] = _prompt_choice(
        "Activity level (sedentary/light/moderate/very/extra): ",
        choices=("sedentary", "light", "moderate", "very", "extra"),
        default=_safe_default_choice(profile.get("activity_level"), ("sedentary", "light", "moderate", "very", "extra"), "moderate"),
    )    

def _wizard_goals(env: Environment, units: str) -> None:
    cprint("\n[bold]Goals setup[/bold]")
    g = env.goals
    c = env.config

    goal_type = _prompt_choice(
        "Goal type (lose/maintain/gain): ",
        choices=("lose", "maintain", "gain"),
        default=_safe_default_choice(g.get("goal_type"), ("lose","maintain","gain"), "maintain"),
    )
    g["goal_type"] = goal_type

    # Start weight default from profile weight if available
    profile_weight = env.profile.get("weight_kg")
    if g.get("start_weight") in (None, "", 0) and profile_weight not in (None, ""):
        g["start_weight"] = profile_weight

    if goal_type == "maintain":
        # Keep goal fields clean
        g["weekly_rate"] = None
        g["target_weight"] = None
    else:
        if units == "imperial":
            imperial_weekly_rate = _prompt_number("Weekly rate (lb/week, e.g. 0.5): ", min_=0.1, default=g.get("weekly_rate"))
            imperial_target_weight = _prompt_number("Target weight (lb): ", min_=1, default=g.get("target_weight"))
            g["weekly_rate"] = lb_to_kg(imperial_weekly_rate)
            g["target_weight"] = lb_to_kg(imperial_target_weight)  
        else:
            g["weekly_rate"] = _prompt_number("Weekly rate (kg/week, e.g. 0.25): ", min_=0.05, default=g.get("weekly_rate"))
            g["target_weight"] = _prompt_number("Target weight (kg): ", min_=1, default=g.get("target_weight"))

    mode = _prompt_choice(
        "Calorie target mode (auto/manual): ",
        choices=("auto", "manual"),
        default=_safe_default_choice(c.get("calorie_target_mode"), ("auto","manual"), "auto"),
    )
    c["calorie_target_mode"] = mode

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


def _safe_units(cfg: Dict[str, Any]) -> str:
    u = str((cfg or {}).get("units", "")).strip().lower()
    return u if u in {"imperial", "metric"} else "imperial"


def _safe_default_choice(current: Any, choices: Tuple[str, ...], fallback: str) -> str:
    cur = str(current or "").strip().lower()
    return cur if cur in {c.lower() for c in choices} else fallback