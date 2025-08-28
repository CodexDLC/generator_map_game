from dataclasses import dataclass
import time, random
from typing import Literal

TILE = {
    "FLOOR": 0,
    "WALL": 1,
    "WATER_DEEP": 2,
    "BORDER": 3,
    "ROAD": 4,
    "GRASS": 5,
    "FOREST": 6,
    "MOUNTAIN": 7,
}

PASSABLE_DEFAULT = {TILE["FLOOR"]}

PNG_COLORS = {
    TILE["FLOOR"]:      "#FFFFFF",
    TILE["WALL"]:       "#000000",
    TILE["WATER_DEEP"]: "#3366FF",
    TILE["BORDER"]:     "#222222",
    TILE["ROAD"]:       "#D1B280",
    TILE["GRASS"]:      "#9AD37F",
    TILE["FOREST"]:     "#3A7A39",
    TILE["MOUNTAIN"]:   "#777777",
}

DEFAULT_TILE_RULES = {
    "floor":       {"base_passable": True,  "move_cost": 1},
    "road":        {"base_passable": True,  "move_cost": 1},
    "grass":       {"base_passable": True,  "move_cost": 2},
    "forest":      {"base_passable": True,  "move_cost": 3},
    "mountain":    {"base_passable": True,  "move_cost": 4},
    "water_deep":  {"base_passable": False, "requires_any": ["amphibious"], "cost_with": {"amphibious": 2}},
    "wall":        {"base_passable": False},
    "border":      {"base_passable": False},
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
    # режимы/граница
    mode: Literal["cave","rooms"] = "cave"
    diag: bool = False
    biome: str = "default"
    features: dict = None
    move_cost: dict[int,int] = None
    spawn_weight: dict[int,float] = None
    encoding: Literal["tiles_v0","rle_rows_v1"] = "tiles_v0"
    border_mode: str = "cliff"      # cliff|wall|void
    border_outer_cells: int = 1
    fall_behavior: str = "kill"

    validate_for: tuple[str,...] = ()     # напр. ("levitation","freeze_water")
    allow_no_base_path: bool = True       # без умений путь можно не гарантировать
    tile_rules: dict | None = None        # переопределить дефолты



    def __post_init__(self):
        if self.features is None:
            self.features = {"water": True, "links": False, "portals": False}
        if self.move_cost is None:
            self.move_cost = {0:1, 1:9999, 2:9999}
        if self.spawn_weight is None:
            self.spawn_weight = {0:1.0, 2:0.1}
        if self.tile_rules is None:
            self.tile_rules = DEFAULT_TILE_RULES

def init_rng(seed: int | str):
    actual = int(time.time()) if seed == "auto" else int(seed)
    return random.Random(actual), actual


