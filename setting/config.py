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
    scale: float = 3000.0
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