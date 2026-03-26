from __future__ import annotations 
from core.data_manager import _parse_birthdate,_compute_age_years

def mifflin_st_jeor_rmr(age: int, sex: str, weight_kg: float, height_cm: float) -> float: 
    sex = sex.strip().lower() 
    
    if sex not in {"male", "female"}: 
        raise ValueError("sex must be 'male' or 'female' for bmr") 
   
    sex_constant = 5 if sex == "male" else -161
    rmr = (10*weight_kg) + (6.25*height_cm) - (5 * age) + sex_constant 
    
    return rmr 
    
def get_rmr_from_profile(profile: dict) -> float:  
    bd = _parse_birthdate(profile.get("birthdate", "")) 
    if bd is None: 
        raise ValueError("Profile is missing a valid birthdate.") 
    age = _compute_age_years(bd) 
   
    sex = profile["sex_for_bmr"] 
    weight = float(profile["weight_kg"])
    height = float(profile["height_cm"])
    
    return mifflin_st_jeor_rmr(age, sex, weight, height) 
 
   
def get_tdee_from_rmr(rmr: float, activity_level: str) -> float: 
    mults = {
        "sedentary": 1.2, 
        "light": 1.375, 
        "moderate": 1.55, 
        "very": 1.725, 
        "extra": 1.9,
    }
    activity_level = activity_level.strip().lower() 
    
    if activity_level not in mults: 
        raise ValueError("Invalid activity level") 
    return rmr * mults[activity_level]


   