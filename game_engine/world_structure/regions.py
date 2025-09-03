# game_engine/world_structure/regions.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Tuple, List, Dict
import random

# --- ИЗМЕНЕНИЕ: В Region теперь будет храниться план дорог для всех чанков внутри него ---
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
    Отвечает за вычисление координат и генерацию/загрузку данных региона.
    """

    def __init__(self, world_seed: int, region_size: int = 5):
        if region_size % 2 == 0:
            raise ValueError("Размер региона должен быть нечетным (3, 5, 7...), чтобы иметь центр.")

        self.world_seed = world_seed
        self.region_size = region_size
        self.cache: dict[Tuple[int, int], Region] = {}

    def get_region_coords_from_chunk_coords(self, cx: int, cz: int) -> Tuple[int, int]:
        """
        Главная функция: определяет, к какому региону принадлежит чанк.
        Использует целочисленное деление.
        """
        # Эта формула корректно работает и для отрицательных координат
        scx = cx // self.region_size
        scz = cz // self.region_size
        return scx, scz

    def get_chunk_coords_in_region(self, cx: int, cz: int) -> Tuple[int, int]:
        """Возвращает локальные координаты чанка внутри его региона (от 0 до 4)."""
        local_cx = cx % self.region_size
        local_cz = cz % self.region_size
        return local_cx, local_cz

    # --- НОВАЯ ФУНКЦИЯ: Глобальное планирование дорог ---
    def _plan_regional_roads(self, scx: int, scz: int) -> Dict[Tuple[int, int], List[str]]:
        """
        Создает высокоуровневый, детерминированный план магистральных дорог для всего региона.
        """
        plan: Dict[Tuple[int, int], List[str]] = {}
        rng = random.Random((self.world_seed * 1009) ^ (scx * 1013) ^ (scz * 1019))

        # 1. Определяем "магистральные выходы" на внешних границах региона
        has_north_exit = rng.random() > 0.3  # 70% шанс
        has_south_exit = rng.random() > 0.3
        has_west_exit = rng.random() > 0.3
        has_east_exit = rng.random() > 0.3

        # Центр региона (например, 2 для размера 5)
        center = self.region_size // 2

        # Глобальные координаты центрального чанка региона
        center_cx = scx * self.region_size + center
        center_cz = scz * self.region_size + center

        # 2. Прокладываем "виртуальные" магистрали от центра к выходам
        if has_north_exit:
            for i in range(center + 1):
                cz = center_cz - i
                plan.setdefault((center_cx, cz), []).extend(['N', 'S'])
        if has_south_exit:
            for i in range(center + 1):
                cz = center_cz + i
                plan.setdefault((center_cx, cz), []).extend(['N', 'S'])
        if has_west_exit:
            for i in range(center + 1):
                cx = center_cx - i
                plan.setdefault((cx, center_cz), []).extend(['W', 'E'])
        if has_east_exit:
            for i in range(center + 1):
                cx = center_cx + i
                plan.setdefault((cx, center_cz), []).extend(['W', 'E'])

        # 3. Убираем дубликаты и "тупики" на краях
        for (cx, cz), sides in plan.items():
            # Убираем дубликаты, сохраняя порядок
            unique_sides = list(dict.fromkeys(sides))

            # Удаляем "тупиковые" выходы (например, 'N' для самого северного чанка)
            local_cx, local_cz = self.get_chunk_coords_in_region(cx, cz)
            if local_cz == 0: unique_sides = [s for s in unique_sides if s != 'N']
            if local_cz == self.region_size - 1: unique_sides = [s for s in unique_sides if s != 'S']
            if local_cx == 0: unique_sides = [s for s in unique_sides if s != 'W']
            if local_cx == self.region_size - 1: unique_sides = [s for s in unique_sides if s != 'E']

            plan[(cx, cz)] = unique_sides

        return plan

    def get_region_data(self, scx: int, scz: int) -> Region:
        """
        Получает данные для региона. Теперь также генерирует и кэширует план дорог.
        """
        if (scx, scz) in self.cache:
            return self.cache[(scx, scz)]

        print(f"[RegionManager] Generating data for new region ({scx}, {scz})...")

        # --- ИЗМЕНЕНИЕ: Вызываем новую функцию планирования ---
        road_plan = self._plan_regional_roads(scx, scz)

        new_region = Region(scx=scx, scz=scz, road_plan=road_plan)

        self.cache[(scx, scz)] = new_region
        return new_region