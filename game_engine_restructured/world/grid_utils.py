# game_engine/world_structure/grid_utils.py
from __future__ import annotations
from typing import List, Dict, Any, Tuple
from ..core.grid.hex import HexGridSpec
import numpy as np


def region_key(cx: int, cz: int, region_size: int) -> Tuple[int, int]:
    """Calculates the region's unique key (scx, scz) from chunk coordinates."""
    offset = region_size // 2
    scx = (
        (cx + offset) // region_size if cx >= -offset else (cx - offset) // region_size
    )
    scz = (
        (cz + offset) // region_size if cz >= -offset else (cz - offset) // region_size
    )
    return scx, scz


def region_base(scx: int, scz: int, region_size: int) -> Tuple[int, int]:
    """Calculates the base chunk coordinates (cx, cz) of a region's top-left corner."""
    offset = region_size // 2
    base_cx = scx * region_size - offset
    base_cz = scz * region_size - offset
    return base_cx, base_cz


PROCESSING_PRIORITY = {
    "obstacle_prop": 0,  # Самый важный
    "water": 1,
    "road": 2,
    "slope": 3,
    "forest_ground": 4,
    "sand": 5,
    "ground": 6,  # Самый низкий приоритет
}


def _get_pixel_to_hex_map(grid_spec: HexGridSpec) -> np.ndarray:
    """
    Создает карту-преобразователь (lookup table), которая для каждого пикселя
    хранит ID гекса, которому он принадлежит.
    """
    size = grid_spec.chunk_px
    # Создаем сетку пиксельных координат
    px_coords_x, px_coords_z = np.meshgrid(np.arange(size), np.arange(size))

    # Находим центры каждого пикселя в мировых координатах
    world_x = (px_coords_x + 0.5) * grid_spec.meters_per_pixel
    world_z = (px_coords_z + 0.5) * grid_spec.meters_per_pixel

    # Преобразуем мировые координаты центров в гексагональные
    # (векторизованная версия world_to_axial)
    qf = (np.sqrt(3.0) / 3.0 * world_x - (1.0 / 3.0) * world_z) / grid_spec.edge_m
    rf = ((2.0 / 3.0) * world_z) / grid_spec.edge_m
    xf, zf = qf, rf
    yf = -xf - zf
    rx, ry, rz = np.round(xf), np.round(yf), np.round(zf)
    dx, dy, dz = np.abs(rx - xf), np.abs(ry - yf), np.abs(rz - zf)
    mask1 = (dx > dy) & (dx > dz)
    rx[mask1] = -ry[mask1] - rz[mask1]
    mask2 = ~mask1 & (dy > dz)
    ry[mask2] = -rx[mask2] - rz[mask2]
    mask3 = ~mask1 & ~mask2
    rz[mask3] = -rx[mask3] - ry[mask3]

    return np.stack([rx.astype(int), rz.astype(int)], axis=-1)


def generate_hex_map_from_pixels(
        grid_spec: HexGridSpec,
        surface_grid: List[List[str]],
        nav_grid: List[List[str]],
        height_grid: List[List[float]],
) -> Dict[str, Any]:
    """
    Создает словарь с данными для каждого гекса, используя метод приоритетов.
    """
    pixel_to_hex_map = _get_pixel_to_hex_map(grid_spec)

    hex_data: Dict[Tuple[int, int], Dict[str, Any]] = {}

    size = grid_spec.chunk_px
    for pz in range(size):
        for px in range(size):
            q, r = pixel_to_hex_map[pz, px]
            hex_coords = (q, r)

            # Собираем данные по пикселю
            nav_type = nav_grid[pz][px]
            surface_type = surface_grid[pz][px]
            height = height_grid[pz][px]

            # Определяем приоритет
            pixel_type = nav_type if nav_type != "passable" else surface_type
            priority = PROCESSING_PRIORITY.get(pixel_type, 99)

            if hex_coords not in hex_data:
                hex_data[hex_coords] = {
                    "heights": [height],
                    "dominant_type": pixel_type,
                    "min_priority": priority
                }
            else:
                hex_data[hex_coords]["heights"].append(height)
                if priority < hex_data[hex_coords]["min_priority"]:
                    hex_data[hex_coords]["min_priority"] = priority
                    hex_data[hex_coords]["dominant_type"] = pixel_type

    # Финальная сборка ответа
    final_hex_map = {}
    for (q, r), data in hex_data.items():
        avg_height = sum(data["heights"]) / len(data["heights"])
        final_type = data["dominant_type"]

        # Определяем итоговую проходимость
        is_passable = final_type not in ["obstacle_prop", "water"]

        key = f"{q},{r}"
        final_hex_map[key] = {
            "type": final_type,
            "nav": "passable" if is_passable else "impassable",
            "height": round(avg_height, 2),
            "cost": 1,  # Базовая стоимость передвижения
            "flags": 0  # Поле для будущих флагов (например, "is_quest_zone")
        }

    return final_hex_map