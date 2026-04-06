# Multipurpose Health Tool

A terminal-based health and nutrition tracker built in Python with a focus on clean architecture, resilient local persistence, and a practical day-to-day logging workflow.

The application helps users manage calorie intake, macronutrients, hydration, custom foods, recipes, and reusable meals from a Rich-powered command-line interface. It also includes an optional USDA FoodData Central import pipeline so the tracker can scale from a lightweight personal logger into a much more capable nutrition lookup tool.

---

## Overview

This project was designed as a modular personal health tool rather than a single-purpose calorie counter. It combines:

- **Interactive terminal UI** for guided data entry and navigation
- **Structured profile and goal setup** for personalized calorie targets
- **Persistent JSON storage** with atomic writes and corruption recovery
- **Expandable nutrition logging** through custom foods, recipes, meals, and optional USDA data import
- **Separation of concerns** between interface, business logic, and persistence layers

From a software engineering perspective, the project emphasizes maintainability and reliability: the codebase is organized into focused modules, user data is stored safely, and the application is structured to support future additions such as biometrics and trend reporting.

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
- Supports **automatic** calorie targets or **manual** calorie targets

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
- Daily dashboard includes water intake progress

### Reusable nutrition data
- Create, edit, and delete **custom foods**
- Mark custom items as drinks and store volume per serving
- Create **custom recipes** composed of multiple ingredients
- Automatically sum recipe nutrition from its ingredients
- Create **custom meals** as reusable groups of multiple food items
- Re-log saved foods, recipes, and meals without repeated manual entry

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
- Main dashboard provides an at-a-glance daily summary of:
  - calories consumed
  - calorie target
  - estimated deficit/surplus relative to target
  - estimated RMR/TDEE
  - hydration progress
  - current, start, and target weight when available
- Uses Rich tables, panels, rules, and progress-style visual elements for readability

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
- Activity multipliers for TDEE estimation
- Goal-aware calorie target logic for weight loss, maintenance, or gain

### Architecture
- `core/` contains business logic, persistence, calculations, dashboard logic, unit conversions, and import/database utilities
- `interface/` contains menu flows, prompts, and terminal UI behavior
- `main.py` boots the environment, runs the setup wizard if needed, and launches the menu system

### Storage strategy
- Core application data is stored as JSON for transparency and simplicity
- USDA nutrition search data is stored separately in SQLite for efficient querying at scale
- Log data is partitioned by month (`YYYY-MM.json`) instead of accumulating into a single ever-growing file

---

## Project Structure

```text
src/
├── core/
│   ├── console_manager.py      # Rich console helpers
│   ├── dashboard_manager.py    # Daily summary + dashboard rendering
│   ├── data_manager.py         # JSON persistence, defaults, recovery, environment loading
│   ├── fdc_importer.py         # USDA JSON/ZIP import -> local SQLite database
│   ├── health_manager.py       # RMR/TDEE and calorie-target logic
│   ├── log_manager.py          # Daily/monthly log storage and aggregate queries
│   ├── menu_manager.py         # Menu registry / dispatch
│   ├── setup_wizard.py         # First-run onboarding flow
│   └── units.py                # Unit conversions
│
├── interface/
│   ├── common.py               # Reusable menu abstractions
│   ├── menu_biometrics.py      # Biometrics menu scaffold
│   ├── menu_food_diary.py      # Food logging, custom foods, recipes, meals, FDC search
│   ├── menu_main.py            # Main application menu
│   ├── menu_settings.py        # Units + USDA database management
│   ├── menu_title_screen.py    # Title screen UI
│   └── prompts.py              # Shared prompt/validation helpers
│
├── data/
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

### Installation

```bash
git clone https://github.com/Cameron-Guinnee/Multipurpose-Health-Tool.git
cd Multipurpose-Health-Tool
pip install rich
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

This design keeps the base application lightweight while still allowing a much larger nutrition dataset when desired.

---

## Engineering Value

This project showcases several skills that are relevant to production software work:

- **Python application design** with modular organization
- **CLI/terminal UX** using Rich for structured, readable interfaces
- **Data modeling** for profiles, goals, daily logs, foods, recipes, and meals
- **Robust file handling** with atomic writes and corruption recovery
- **SQLite + full-text search** integration for scalable local querying
- **Domain logic implementation** for calorie targets and nutrition tracking
- **Extensible architecture** that leaves room for future feature growth without requiring a rewrite

---

## Current Limitations

To keep the README accurate, a few parts of the broader vision are still in progress:

- The **Biometrics** menu is currently a scaffold and not yet exposed as a full user workflow
- Weight-aware dashboard logic exists, but comprehensive weight/history tracking is not yet surfaced through the UI
- Exercise logging and longer-term trend summaries are planned rather than fully implemented

---

## Roadmap

Planned areas for future development include:

- Full biometrics workflows (weight, blood pressure, measurements)
- Weekly and monthly nutrition summaries
- Exercise logging and calorie adjustment support
- Trend visualization for body weight and intake data
- Expanded settings and reporting options

---

## Why this project stands out

Unlike a basic CRUD-style tracker, this application combines interactive CLI design, health-related calculation logic, resilient local storage, reusable nutrition abstractions, and optional large-dataset search integration in a single cohesive tool. It is a strong portfolio project for demonstrating practical Python engineering beyond small scripts.
