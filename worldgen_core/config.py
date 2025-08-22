from dataclasses import dataclass

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
    version: str = "v1"   # <- Новая папка версии (например, v20250822_1530)
