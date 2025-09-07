from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class Player:
    # Мировые координаты
    wx: int = 0
    wz: int = 0

    # Путь для движения (список мировых координат)
    path: List[Tuple[int, int]] = field(default_factory=list)

    # Таймер для плавного движения по пути
    move_timer: float = 0.0
