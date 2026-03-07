from typing import Callable, Any 
from dataclasses import dataclass 


@dataclass(frozen=True)
class MenuItem:
    key: str
    label: str
    action: Callable[[Any], None]