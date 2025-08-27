from dataclasses import dataclass, field
from typing import List


@dataclass
class BiomeConfig:
    ocean_level_m: float = 0.0
    beach_height_m: float = 5.0
    rock_height_m: float = 500.0
    snow_height_m: float = 1000.0
    max_grass_slope_deg: float = 40.0


@dataclass
class GenConfig:
    out_dir: str = "./out"
    world_id: str = "demo"
    seed: int = 12345
    width: int = 1024
    height: int = 1024
    chunk: int = 512

    plains_scale: float = 4000.0
    plains_octaves: int = 4
    mountains_scale: float = 1000.0
    mountains_octaves: int = 8
    mask_scale: float = 5000.0

    # Новый параметр для контроля высоты гор
    mountain_strength: float = 0.6

    height_distribution_power: float = 1.0
    lacunarity: float = 2.0
    gain: float = 0.5
    with_biomes: bool = True

    origin_x: int = 0
    origin_y: int = 0
    meters_per_pixel: float = 1.0
    land_height_m: float = 150.0  # Теперь это только "линейка" для биомов
    version: str = "v1"
    export_for_godot: bool = True

    biome_config: BiomeConfig = field(default_factory=BiomeConfig)

    lods: List[int] = field(default_factory=lambda: [2, 4])
    navgrid_cell_m: float = 2.0
    navgrid_max_slope_deg: float = 40.0
    navgrid_block_water: bool = True

    # temp_equator_C = 24.0, temp_pole_C = -6.0, temp_axis_deg = 0.0,
    # temp_lapse_C_per_km = 6.5, temp_noise_scale_m = 12000.0, temp_noise_amp_C = 4.0

    # в dataclass GenConfig
    volcano_enable: bool = False
    volcano_center_px: tuple[int, int] | None = None  # None = центр карты
    volcano_radius_m: float = 2500.0
    crater_radius_m: float = 300.0
    peak_add_m: float = 120.0
    island_radius_m: float = 9000.0
    island_band_m: float = 2000.0
    ridge_noise_amp: float = 0.10


    def validate(self):
        if not self.out_dir or not self.world_id:
            raise ValueError("Поля 'Output dir' и 'World ID' не могут быть пустыми.")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Размер карты (ширина и высота) должен быть больше нуля.")