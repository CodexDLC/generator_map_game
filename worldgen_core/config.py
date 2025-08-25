from dataclasses import dataclass, field
from typing import List

@dataclass
class GenConfig:
    out_dir: str
    world_id: str
    seed: int
    width: int
    height: int
    chunk: int = 512
    scale: float = 1000.0
    octaves: int = 3
    lacunarity: float = 2.0
    gain: float = 0.5
    with_biomes: bool = False
    ocean_level: float = 0.10
    edge_boost: float = 0.0
    edge_margin_frac: float = 0.12
    origin_x: int = 0
    origin_y: int = 0
    meters_per_pixel: float = 5.0
    # --- ИЗМЕНЕНИЕ: Новый, понятный параметр ---
    land_height_m: float = 500.0 # Максимальная высота суши в метрах
    version: str = "v1"
    export_for_godot: bool = False

    # --- Поля для старого функционала (оставляем) ---
    lods: List[int] = field(default_factory=lambda: [2, 4])
    navgrid_cell_m: float = 2.0
    navgrid_max_slope_deg: float = 40.0
    navgrid_block_water: bool = True