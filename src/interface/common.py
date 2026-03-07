from core.data_manager import Environment
from typing import Callable 
from dataclasses import dataclass 


@dataclass(frozen=True)
class MenuItem:
    key: str
    label: str
    action: Callable[[Environment], None]