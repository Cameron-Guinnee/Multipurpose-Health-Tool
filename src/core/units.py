from __future__ import annotations 

def lb_to_kg(weight_lb: float) -> float: 
    kilograms = weight_lb * 0.45359237
    return kilograms 
    
def kg_to_lb(weight_kg: float) -> float: 
    pounds = weight_kg * 2.20462
    return pounds 

def in_to_cm(height_in: float) -> float: 
    centimeters = height_in * 2.54
    return centimeters 

def cm_to_in(height_cm: float) -> float: 
    inches = height_cm/2.54
    return inches 