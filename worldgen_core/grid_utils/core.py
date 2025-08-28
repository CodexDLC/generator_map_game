from dataclasses import dataclass
import time
import random
from typing import Literal

# Коды тайлов (v0)
TILE = {
    "FLOOR": 0,
    "WALL": 1,
    "WATER": 2,
}

# Что считаем проходимым (для BFS/валидаций)
PASSABLE_DEFAULT = {TILE["FLOOR"]}

# Цвета превью PNG
PNG_COLORS = {
    TILE["FLOOR"]: "#FFFFFF",
    TILE["WALL"]:  "#000000",
    TILE["WATER"]: "#3366FF",
}

@dataclass
class GenParams:
    seed: int | str
    w: int
    h: int
    wall_chance: float
    open_min: float = 0.55
    water_scale: float = 15.0
    water_thr: float = 0.6
    cell_size: float = 1.0
    levels: int = 1
    chunk_size: int = 64

    # v1/v2
    mode: Literal["cave","rooms"] = "cave"
    diag: bool = False
    biome: str = "default"
    features: dict = None
    move_cost: dict[int,int] = None
    spawn_weight: dict[int,float] = None
    encoding: Literal["tiles_v0","rle_rows_v1"] = "tiles_v0"

    def __post_init__(self):
        if self.features is None:
            self.features = {"water": True, "links": False, "portals": False}
        if self.move_cost is None:
            self.move_cost = {0:1, 1:9999, 2:9999}  # FLOOR=1, WALL/WATER=∞
        if self.spawn_weight is None:
            self.spawn_weight = {0:1.0, 2:0.1}      # базово для v0


def init_rng(seed: int | str):
    """Возвращает (rng, actual_seed). Поддерживает seed='auto'."""
    if seed == "auto":
        actual = int(time.time())
    else:
        actual = int(seed)
    return random.Random(actual), actual