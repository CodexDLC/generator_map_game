from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class Player:
    # Гексагональные координаты
    q: int = 0
    r: int = 0

    # Путь для движения (список гексагональных координат)
    path: List[Tuple[int, int]] = field(default_factory=list)

    # Таймер для плавного движения по пути
    move_timer: float = 0.0