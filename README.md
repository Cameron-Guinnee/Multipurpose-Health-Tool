# Multipurpose Health Tool

A terminal-based personal health tracking application built in Python. Tracks daily nutrition, food diary entries, water intake, and biometric data, with calorie targets calculated automatically from user profile data.

---

## Features

- **Food Diary** — Log meals by category (breakfast, lunch, dinner, snack), with full macro breakdown (calories, protein, carbs, fat) and a running daily total
- **Custom Food Items** — Predefine reusable foods with their nutrition info and log them in seconds with a quantity multiplier, skipping repetitive data entry
- **Water Tracking** — Log water intake in oz or mL with a per-session breakdown
- **Calorie Targets** — Automatically calculated from profile data using the Mifflin-St Jeor RMR equation and an activity-level TDEE multiplier, or set manually
- **Dashboard** — At-a-glance daily summary rendered on every screen, showing calories consumed vs. target and macro totals
- **Imperial & Metric support** — All inputs and displays adapt to the user's chosen unit system
- **Persistent storage** — All data is saved locally as JSON, with atomic writes, corruption recovery, and automatic default-file creation on first run

---

## Tech Stack

- **Python 3.x**
- **[Rich](https://github.com/Textualize/rich)** — terminal tables, styled output, and layout
- JSON flat-file storage with atomic write safety (`os.replace` on a `.tmp` file)

---

## Project Structure

```
src/
├── core/
│   ├── data_manager.py       # JSON persistence, defaults, atomic I/O, Environment loader
│   ├── log_manager.py        # Monthly log files, daily entry helpers, aggregate queries
│   ├── health_manager.py     # RMR (Mifflin-St Jeor) and TDEE calculations
│   ├── dashboard_manager.py  # Dashboard rendering logic
│   ├── console_manager.py    # Thin wrappers around Rich console I/O
│   └── menu_manager.py       # Menu routing
├── interface/
│   ├── menu_main.py          # Top-level menu and navigation
│   ├── menu_food_diary.py    # Food diary, custom foods, water logging
│   ├── menu_biometrics.py    # Biometrics menu (in progress)
│   ├── menu_settings.py      # Settings menu
│   └── prompts.py            # Reusable input prompt helpers
├── data/                     # Auto-created on first run, excluded from version control
│   ├── config.json
│   ├── profile.json
│   ├── goals.json
│   ├── custom_foods.json
│   └── logs/
│       └── YYYY-MM.json
└── main.py
```

---

## Getting Started

**Prerequisites:** Python 3.10+

1. Clone the repository:
   ```bash
   git clone https://github.com/Cameron-Guinnee/Multipurpose-Health-Tool.git
   cd Multipurpose-Health-Tool
   ```

2. Install dependencies:
   ```bash
   pip install rich
   ```

3. Run the application:
   ```bash
   python src/main.py
   ```

On first launch a setup wizard will guide you through creating your profile. The `src/data/` directory and all data files are created automatically.

---

## Design Notes

A few implementation decisions worth highlighting:

- **Atomic writes** — all JSON saves write to a `.tmp` file first, then use `os.replace()` to swap it in, preventing data corruption from interrupted writes
- **Corruption recovery** — if a JSON file fails to parse on load, it is renamed to `.corrupt-<timestamp>.json` and rebuilt from defaults automatically
- **Separation of concerns** — persistence (`data_manager`, `log_manager`), business logic (`health_manager`), and UI (`interface/`) are kept strictly separate; no I/O in the core layer
- **Logs stored by month** — daily entries are grouped into `YYYY-MM.json` files rather than one file per day or one growing file, keeping I/O efficient as data accumulates

---

## Roadmap

- [ ] Biometrics tracking (weight history, blood pressure, measurements)
- [ ] Weight trend charts in the terminal
- [ ] Weekly and monthly nutrition summaries
- [ ] Exercise logging and calorie adjustment
- [ ] Settings menu (unit switching, manual calorie target)
