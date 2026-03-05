from __future__ import annotations 
from core import data_manager 
from core import units 
from core.console_manager import cprint,cinput 



def mifflin_st_jeor_rmr(age: int, sex: str, weight_kg: float, height_cm: float) -> float: 
    gender = gender.strip().lower() 
    
    if sex not in {"male", "female"}: 
        raise ValueError("sex must be 'male' or 'female' for bmr") 
   
    sex_constant = 5 if sex == "male" else -161
    rmr = (10*weight_kg) + (6.25*height_cm) - (5 * age) + sex_constant 
    
    return rmr 
    
def get_rmr_from_profile(profile: dict) -> float:  
    age = int(float(profile["age"])), 
    sex = profile["sex_for_bmr"] 
    weight = imperial_to_metric(profile["weight"]) if units == "imperial" else profile["weight"]
    height = imperial_to_metric(profile["height"]) if units == "imperial" else profile["height"] 
    
    return mifflin_st_jeor_rmr(age, sex, weight, height) 
 
   
def get_tdee_from_rmr(rmr: float, activity_level: str) -> float: 
    mults = {
        "sedentary": 1.2, 
        "light": 1.375, 
        "moderate": 1.55, 
        "very_active": 1.725, 
        "extra_active": 1.9,
    }
    activity_level = activity_level.strip().lower() 
    
    if activity_level not in mults: 
        raise ValueError("Invalid activity level") 
    return rmr * mults[activity_level]


    
    

# This, at face value, seems a bit unnecessary and redundant? 
"""
def tdee_from_profile(profile: dict) -> float: 
    rmr = mifflin_st_jeor_rmr( 
        age = int(float(profile["age"])), 
        gender = profile["gender"], 
        weight_lb = float(profile["weight"]), 
        height_in = float(profile["height"]), 
    ) 
    return tdee_from_rmr(rmr, profile["activity_level"]) 
"""