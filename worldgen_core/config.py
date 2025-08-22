from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class GenConfig:
    out_dir: str
    world_id: str
    seed: int
    width: int
    height: int
    chunk: int = 512
    scale: float = 3000.0
    octaves: int = 6
    lacunarity: float = 2.0
    gain: float = 0.5
    with_biomes: bool = False
    ocean_level: float = 0.10
    edge_boost: float = 0.0
    edge_margin_frac: float = 0.12
    origin_x: int = 0
    origin_y: int = 0
    meters_per_pixel: float = 1.0
    height_range_m: float = 200.0
    import_vertical_scale_m: Optional[float] = None
    version: str = "v1"

    # доп. опции (по умолчанию не обязательны в GUI)
    overview_map_px: int = 0                     # 0=выкл
    lods: List[int] = field(default_factory=lambda: [2, 4])
    navgrid_enabled: bool = False
    navgrid_cell_m: float = 1.0
    navgrid_max_slope_deg: float = 35.0
    navgrid_block_water: bool = True

    # подсказки клиенту
    active_chunk_radius: int = 3
    target_vertex_pitch_m: float = 2.0
