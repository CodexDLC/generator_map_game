# game_engine/world_structure/regions.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Tuple, List, Dict

# --- Импортируем наших планировщиков ---
from .planners import road_planner
from .planners import biome_planner # <-- РАСКОММЕНТИРОВАЛИ И ПОДКЛЮЧИЛИ


@dataclass
class Region:
    """Хранит все метаданные для одного региона (суперчанка)."""
    scx: int
    scz: int
    biome_type: str = "placeholder_biome"
    difficulty: float = 1.0
    # Ключ - коорд. чанка (cx, cz), значение - список сторон ('N', 'S', 'W', 'E'), куда должны идти дороги
    road_plan: Dict[Tuple[int, int], List[str]] = field(default_factory=dict)


class RegionManager:
    """
    Главный класс для управления сеткой регионов (суперчанков).
    Отвечает за вычисление координат и вызов планировщиков для генерации данных региона.
    """

    def __init__(self, world_seed: int, region_size: int = 7):
        if region_size % 2 == 0:
            raise ValueError("Размер региона должен быть нечетным (3, 5, 7...), чтобы иметь центр.")

        self.world_seed = world_seed
        self.region_size = region_size
        self.cache: dict[Tuple[int, int], Region] = {}

    def get_region_coords_from_chunk_coords(self, cx: int, cz: int) -> Tuple[int, int]:
        """
        Стандартная функция: определяет, к какому региону принадлежит чанк.
        Использует простое целочисленное деление.
        """
        scx = cx // self.region_size
        scz = cz // self.region_size
        return scx, scz

    def get_chunk_coords_in_region(self, cx: int, cz: int) -> Tuple[int, int]:
        """Возвращает локальные координаты чанка внутри его региона (от 0 до 6)."""
        local_cx = cx % self.region_size
        local_cz = cz % self.region_size
        return local_cx, local_cz

    def get_region_data(self, scx: int, scz: int) -> Region:
        """
        Получает или генерирует данные для региона, вызывая внешние планировщики.
        """
        if (scx, scz) in self.cache:
            return self.cache[(scx, scz)]

        print(f"[RegionManager] Generating data for new region ({scx}, {scz})...")

        # 1. Вызываем планировщик дорог
        road_plan = road_planner.plan_roads_for_region(
            scx, scz, self.world_seed, self.region_size
        )

        # 2. Вызываем планировщик биомов, чтобы получить тип биома
        biome_type = biome_planner.assign_biome_to_region(scx, scz, self.world_seed)
        print(f"[RegionManager] -> Assigned biome: '{biome_type}'")


        # 3. Собираем все данные в объект Region
        new_region = Region(
            scx=scx,
            scz=scz,
            road_plan=road_plan,
            biome_type=biome_type
        )

        self.cache[(scx, scz)] = new_region
        return new_region