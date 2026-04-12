# Multipurpose Health Tool

A terminal-based health and nutrition tracker built in Python with a focus on clean architecture, resilient local persistence, and a practical day-to-day logging workflow.

The application helps users manage calorie intake, macronutrients, hydration, custom foods, recipes, reusable meals, biometrics, and weight tracking from a Rich-powered command-line interface. It also includes an optional USDA FoodData Central import pipeline so the tracker can scale from a lightweight personal logger into a much more capable nutrition lookup tool.

---

## Overview

This project was designed as a modular personal health tool rather than a single-purpose calorie counter. It combines:

- **Interactive terminal UI** for guided data entry and navigation
- **Animated title screen** with cross-platform key-press detection
- **Structured profile and goal setup** for personalized calorie targets
- **Persistent JSON storage** with atomic writes and corruption recovery
- **Expandable nutrition logging** through custom foods, recipes, meals, and optional USDA data import
- **Full biometrics tracking** with date navigation and Plotly-powered trend charts
- **Separation of concerns** between interface, business logic, and persistence layers

---

## Current Feature Set

### Personalized onboarding and goal setup
- First-run setup wizard for profile and preferences
- Supports **imperial or metric units**
- Collects profile inputs used for energy calculations:
  - birthdate
  - sex used for BMR/RMR estimation
  - height
  - weight
  - activity level
- Supports goal modes for **lose**, **maintain**, or **gain**
- Supports **automatic** calorie targets (derived from TDEE + weekly rate) or **manual** calorie targets

### Daily nutrition logging
- Log food entries by meal category:
  - breakfast
  - lunch
  - dinner
  - snack
  - drink
  - uncategorized
- Tracks per-entry and daily totals for:
  - calories
  - protein
  - carbohydrates
  - fat
- Delete logged food entries by entry ID
- Navigate the diary by date, including previous days and direct date jumps

### Hydration tracking
- Drink entries contribute to a daily hydration total automatically
- Hydration is displayed in the active unit system:
  - ounces in imperial mode
  - milliliters in metric mode
- Daily dashboard includes water intake progress bar

### Reusable nutrition data
- Create, edit, and delete **custom foods**
- Mark custom items as drinks and store volume per serving
- Create **custom recipes** composed of multiple ingredients (from custom foods, FDC search, or manual entry)
- Automatically sum recipe nutrition from its ingredients
- Create **custom meals** as reusable groups of multiple food items
- Re-log saved foods, recipes, and meals without repeated manual entry

### Biometrics tracking
- Log and review biometric entries by date with full date navigation
- Supported metrics:
  - **Weight** (kg / lbs) — syncs back to the user profile automatically
  - **Blood Pressure** (systolic + diastolic, mmHg) — displays classification hint on entry
  - **Heart Rate** (bpm)
  - **Waist circumference** (cm / in)
  - **Body fat percentage** (%\)
- All values stored in SI/metric units; converted to the user's preferred unit for display
- Delete biometric entries by ID
- Date-navigable log view: previous/next day, jump to a specific date, return to today

### Biometric trend visualization
- **Plotly-powered HTML trend charts** that open directly in the system browser
- Select any combination of metrics to overlay on a single chart
- Blood pressure systolic and diastolic are always grouped together
- Weight and waist use a secondary y-axis when combined with mmHg or bpm metrics
- Date-range presets: **7 days**, **30 days**, **90 days**, and **all-time**
- Custom date range input
- Cross-platform: uses `webbrowser.open()` so no display server is required from the CLI

### Optional USDA FoodData Central integration
- Import USDA FoodData Central datasets from local **JSON or ZIP** files
- Supports the following dataset families:
  - Foundation Foods
  - SR Legacy
  - Branded Foods
- Builds a local **SQLite** search database for fast lookup
- Uses **FTS5 full-text search** for food searches during logging
- Displays database statistics and supports removal/rebuild from the settings menu

### Dashboard and summaries
- Main dashboard provides an at-a-glance daily summary rendered as three side-by-side Rich panels:
  - **Calories panel**: consumed, target, visual progress bar, delta from target, estimated TDEE, estimated RMR, and planned daily deficit/surplus
  - **Hydration panel**: consumed, goal, visual progress bar
  - **Weight panel**: start, current, and target weight; distance to goal; total change since start
- Dashboard auto-reloads from disk on each menu loop iteration

### Data reliability and persistence
- Stores user/application data locally in JSON
- Uses **atomic writes** to reduce risk of file corruption during saves
- Automatically recreates missing default data files
- Backs up malformed JSON files and rebuilds clean replacements when corruption is detected
- Stores logs in **monthly files** to keep persistence manageable over time

---

## Technical Highlights

### Health calculations
- **Mifflin-St Jeor** equation for resting metabolic rate estimation
- Activity multipliers for TDEE estimation (sedentary, light, moderate, very active, extra active)
- Goal-aware calorie target logic: TDEE ± (weekly_rate_kg × 7700 / 7) kcal/day

### Architecture
- `core/` contains business logic, persistence, calculations, dashboard rendering, and import/database utilities
- `interface/` contains menu flows, prompts, and terminal UI behavior
- `interface/biometrics_core.py` holds shared biometrics constants and helpers to prevent circular imports between `menu_biometrics` and `menu_biometrics_trends`
- `main.py` boots the environment, runs the setup wizard if needed, and launches the menu system

### Storage strategy
- Core application data is stored as JSON for transparency and simplicity
- USDA nutrition search data is stored separately in SQLite for efficient querying at scale
- Log data is partitioned by month (`YYYY-MM.json`) instead of accumulating into a single ever-growing file
- Biometrics are stored in a dedicated `biometrics.json` file, separate from the daily food/activity logs

---

## Project Structure

```text
src/
├── core/
│   ├── console_manager.py      # Rich console helpers
│   ├── dashboard_manager.py    # Daily summary model + three-panel dashboard rendering
│   ├── data_manager.py         # JSON persistence, defaults, recovery, environment loading
│   ├── fdc_importer.py         # USDA JSON/ZIP import → local SQLite database
│   ├── health_manager.py       # RMR/TDEE and calorie-target logic (Mifflin-St Jeor)
│   ├── log_manager.py          # Daily/monthly log storage and aggregate queries
│   ├── menu_manager.py         # Menu registry / dispatch
│   └── setup_wizard.py         # First-run onboarding flow
│
├── interface/
│   ├── biometrics_core.py      # Shared biometrics constants, persistence, unit helpers
│   ├── menu_biometrics.py      # Biometrics log, date navigation, entry/deletion
│   ├── menu_biometrics_trends.py # Plotly trend charts, metric selection, date ranges
│   ├── menu_food_diary.py      # Food logging, custom foods, recipes, meals, FDC search
│   ├── menu_main.py            # Main application menu
│   ├── menu_settings.py        # Units toggle + USDA database management
│   ├── menu_title_screen.py    # Animated title screen (cross-platform key-press)
│   └── shared.py               # MenuItem primitives, menu panel builder, prompt helpers
│
├── data/
│   ├── biometrics.json
│   ├── config.json
│   ├── custom_foods.json
│   ├── custom_meals.json
│   ├── custom_recipes.json
│   ├── goals.json
│   ├── profile.json
│   └── logs/
│       └── YYYY-MM.json
│
└── main.py
```

---

## Getting Started

### Requirements
- Python 3.10+
- `rich`
- `plotly` (required for biometric trend charts)

### Installation

```bash
git clone https://github.com/Cameron-Guinnee/Multipurpose-Health-Tool.git
cd Multipurpose-Health-Tool
pip install rich plotly
```

### Run

```bash
python src/main.py
```

On first launch, the application will guide the user through setup and create the necessary data files automatically.

---

## USDA Database Import

The USDA database is optional. The application works without it, but importing the dataset significantly expands food search capability.

From the settings menu, the user can import USDA FoodData Central datasets from local downloads. The importer accepts either extracted `.json` files or `.zip` archives downloaded from FoodData Central.

Recommended downloads (JSON format, from https://fdc.nal.usda.gov/download-datasets):
- Foundation Foods (~7 MB unzipped)
- SR Legacy (~205 MB unzipped)
- Branded Foods (~3.1 GB unzipped)

This design keeps the base application lightweight while still allowing a much larger nutrition dataset when desired.

---

## Engineering Value

This project showcases several skills that are relevant to production software work:

- **Python application design** with modular organization and clean separation of layers
- **CLI/terminal UX** using Rich for structured, readable interfaces including animated screens
- **Data modeling** for profiles, goals, daily logs, foods, recipes, meals, and biometrics
- **Robust file handling** with atomic writes and corruption recovery
- **SQLite + full-text search** integration for scalable local querying
- **Domain logic implementation** for calorie targets and nutrition tracking
- **Plotly integration** for interactive HTML trend charts launched from a terminal app
- **Circular import avoidance** through deliberate module decomposition (`biometrics_core`)
- **Extensible architecture** that supports future feature additions without requiring a rewrite

---

## Current Limitations

- Exercise logging entry factories exist in `log_manager.py` but the exercise menu and UI are not yet implemented
- Water goal is set automatically based on sex (3.7 L for male, 2.7 L for female); there is no UI to customize it yet
- The `delete_entry` function in `log_manager.py` does not currently support deletion of water, weight, exercise, or biometric entries from the daily log (only food entries by ID); biometric entries have their own dedicated deletion path in `menu_biometrics.py`

---

## Roadmap

Planned areas for future development include:

- Exercise logging UI and calorie adjustment support
- Customizable water goal
- Weekly and monthly nutrition summaries
- Expanded settings and reporting options
