def get_menu(menu_name: str): 
    from interface.menu_main import run_main_menu
    from interface.menu_food_diary import run_food_diary_menu
    from interface.menu_biometrics import run_biometrics_menu
    from interface.menu_settings import run_settings_menu
    
    
    MENUS = { 
        "main_menu": run_main_menu,
        "food_diary_menu": run_food_diary_menu,
        "biometrics_menu": run_biometrics_menu,
        "settings_menu": run_settings_menu
    }
    
    if not menu_name in MENUS: 
        raise ValueError("Invalid menu id")
        
    return MENUS.get(menu_name)
    