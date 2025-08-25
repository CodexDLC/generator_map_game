from dataclasses import dataclass, field
from typing import List


@dataclass
class BiomeConfig:
    """
    Класс для хранения фиксированных высот и углов наклона биомов.
    """
    ocean_level_m: float = 0.0  # Высота, ниже которой находится океан (обычно 0)
    beach_height_m: float = 5.0  # Высота, до которой находится пляж
    rock_height_m: float = 500.0  # Высота, с которой начинается скалистый рельеф
    snow_height_m: float = 1000.0  # Высота, с которой начинается снег
    max_grass_slope_deg: float = 40.0  # Смена земли на скалу


@dataclass
class GenConfig:
    out_dir: str = "./out"
    world_id: str = "demo"
    seed: int = 12345
    width: int = 1024
    height: int = 1024
    chunk: int = 512
    scale: float = 3000.0
    octaves: int = 3
    lacunarity: float = 2.0
    gain: float = 0.5
    with_biomes: bool = True

    create_island: bool = True
    edge_boost: float = 0.0
    edge_margin_frac: float = 0.12
    origin_x: int = 0
    origin_y: int = 0
    meters_per_pixel: float = 1.0
    land_height_m: float = 150.0
    version: str = "v1"
    export_for_godot: bool = False

    biome_config: BiomeConfig = field(default_factory=BiomeConfig)

    lods: List[int] = field(default_factory=lambda: [2, 4])
    navgrid_cell_m: float = 2.0
    navgrid_max_slope_deg: float = 40.0
    navgrid_block_water: bool = True

    def validate(self):
        """Проверяет, что все параметры конфигурации находятся в допустимых пределах."""
        if not self.out_dir or not self.world_id:
            raise ValueError("Поля 'Output dir' и 'World ID' не могут быть пустыми.")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Размер карты (ширина и высота) должен быть больше нуля.")
        if not 0.0 <= self.ocean_level <= 1.0:
            raise ValueError("Уровень океана должен быть в диапазоне от 0.0 до 1.0.")
        if self.edge_margin_frac < 0.0 or self.edge_margin_frac > 1.0:
            raise ValueError("Размер 'пляжной' зоны должен быть в диапазоне от 0.0 до 1.0.")