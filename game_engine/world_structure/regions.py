# game_engine/world_structure/regions.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Tuple, List, Dict
import random

from game_engine.core.utils.rng import edge_key


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
        """Возвращает локальные координаты чанка внутри его региона (от 0 до 4)."""
        local_cx = cx % self.region_size
        local_cz = cz % self.region_size
        return local_cx, local_cz

    def _plan_regional_roads(self, scx: int, scz: int) -> Dict[Tuple[int, int], List[str]]:
        """
        ФИНАЛЬНАЯ ВЕРСИЯ: Создает план "ворот" и гарантирует подведение дорог к городам.
        """
        plan = {}

        # ... (все вспомогательные функции get_border_rng и get_border_chunk_coords остаются без изменений)
        def get_border_rng(neighbor_scx, neighbor_scz):
            key_seed = edge_key(self.world_seed, scx, scz, neighbor_scx, neighbor_scz)
            return random.Random(key_seed)

        def get_border_chunk_coords(side: str, local_pos: int):
            base_cx = scx * self.region_size
            base_cz = scz * self.region_size
            if side == 'N': return base_cx + local_pos, base_cz
            if side == 'S': return base_cx + local_pos, base_cz + self.region_size - 1
            if side == 'W': return base_cx, base_cz + local_pos
            if side == 'E': return base_cx + self.region_size - 1, base_cz + local_pos
            return 0, 0

        gen_north, gen_east, gen_south, gen_west = True, True, True, True
        if scz == 0: gen_south = False
        min_gates = self.region_size // 2
        max_gates = self.region_size

        # --- Шаг 1: Генерируем случайные "ворота" на границах ---
        # ... (весь код генерации north_exits, south_exits, west_exits, east_exits остается без изменений)
        north_exits, south_exits, west_exits, east_exits = set(), set(), set(), set()
        if gen_north:
            rng = get_border_rng(scx, scz - 1)
            k = rng.randint(min_gates, max_gates)
            north_exits.update(rng.sample(range(self.region_size), k))
        if gen_south:
            rng = get_border_rng(scx, scz + 1)
            k = rng.randint(min_gates, max_gates)
            south_exits.update(rng.sample(range(self.region_size), k))
        if gen_west:
            rng = get_border_rng(scx - 1, scz)
            k = rng.randint(min_gates, max_gates)
            west_exits.update(rng.sample(range(self.region_size), k))
        if gen_east:
            rng = get_border_rng(scx + 1, scz)
            k = rng.randint(min_gates, max_gates)
            east_exits.update(rng.sample(range(self.region_size), k))

        # --- Шаг 2: Принудительно добавляем "ворота" для городов в стартовом регионе ---
        if scx == 0 and scz == 0:
            # Для столицы (0,0) нужны выходы во все 4 стороны
            north_exits.add(0)
            south_exits.add(0)
            west_exits.add(0)
            east_exits.add(0)
            # Для порта (0,3) нужны выходы на запад и восток
            west_exits.add(3)
            east_exits.add(3)

        # --- Шаг 3: Прокладываем магистрали (остается без изменений) ---
        # ... (весь код, который прокладывает all_vertical_lanes и all_horizontal_lanes, остается)
        base_cx, base_cz = scx * self.region_size, scz * self.region_size
        all_vertical_lanes = north_exits | south_exits
        for lx in all_vertical_lanes:
            for lz in range(self.region_size):
                cx, cz = base_cx + lx, base_cz + lz
                sides = plan.setdefault((cx, cz), [])
                if lz > 0: sides.append('N')
                if lz < self.region_size - 1: sides.append('S')

        all_horizontal_lanes = west_exits | east_exits
        for lz in all_horizontal_lanes:
            for lx in range(self.region_size):
                cx, cz = base_cx + lx, base_cz + lz
                sides = plan.setdefault((cx, cz), [])
                if lx > 0: sides.append('W')
                if lx < self.region_size - 1: sides.append('E')

        for coord, sides in plan.items():
            plan[coord] = list(dict.fromkeys(sides))

        return plan

    def get_region_data(self, scx: int, scz: int) -> Region:
        """
        Получает данные для региона. Теперь также генерирует и кэширует план дорог.
        """
        if (scx, scz) in self.cache:
            return self.cache[(scx, scz)]

        print(f"[RegionManager] Generating data for new region ({scx}, {scz})...")

        # Вызываем функцию планирования дорог
        road_plan = self._plan_regional_roads(scx, scz)

        new_region = Region(scx=scx, scz=scz, road_plan=road_plan)

        self.cache[(scx, scz)] = new_region
        return new_region