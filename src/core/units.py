from __future__ import annotations 

def imperial_to_metric(weight_lb: float, height_in: float) -> tuple[float, float]:  
    """Converts pounds and inches to their metric equivalents"""
    kilograms = weight_lb * 0.45359237
    centimeters = height_in * 2.54 
    return kilograms,centimeters 
    
def metric_to_imperial(weight_kg: float, height_cm: float) -> tuple[float, float]:  
    pounds = weight_kg * 2.20462
    inches = height_cm/2.54
    return pounds,inches