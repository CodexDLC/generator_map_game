# game_engine/story_features/features.py
from __future__ import annotations
import random
from typing import List, Any
from opensimplex import OpenSimplex

from ..core.constants import KIND_GROUND, KIND_SAND, KIND_TREE, KIND_ROCK, KIND_SLOPE
from ..core.types import GenResult
from ..world_structure.regions import Region


def generate_forests(result: GenResult, preset: Any, region: Region):
    """
    Генерирует леса, используя двухслойный шум и прореживание с защитной зоной.
    Работает со своим собственным набором шумов.
    """
    kind_grid = result.layers["kind"]
    size = len(kind_grid)
    cfg = getattr(preset, "scatter", {})
    if not cfg.get("enabled", False):
        return



    rng = random.Random(result.stage_seeds.get("obstacles", result.seed))
    rng.shuffle(possible_points)

    placement_forbidden = [[False for _ in range(size)] for _ in range(size)]
    tree_count = 0
    rock_count = 0

    for x, z in possible_points:
        if placement_forbidden[z][x]:
            continue

        # С вероятностью 95% это будет дерево, и с 5% - камень
        if rng.random() < 0.95:
            kind_grid[z][x] = KIND_TREE
            tree_count += 1
        else:
            # Камни ставим только если они не находятся на уже существующем дереве/камне
            if kind_grid[z][x] not in (KIND_TREE, KIND_ROCK):
                kind_grid[z][x] = KIND_ROCK
                rock_count += 1

        # Блокируем защитную зону вокруг нового объекта
        for dz in range(-min_dist, min_dist + 1):
            for dx in range(-min_dist, min_dist + 1):
                nx, nz = x + dx, z + dz
                if 0 <= nx < size and 0 <= nz < size:
                    placement_forbidden[nz][nx] = True

    total_count = tree_count + rock_count
    if total_count > 0:
        print(f"--- FOREST: Created {tree_count} trees and {rock_count} rocks for chunk ({result.cx}, {result.cz})")


def generate_rocks(result: GenResult, preset: Any):
    """
    Генерирует скопления камней, преимущественно у подножия склонов.
    Использует свой собственный, однослойный шум.
    """
    kind_grid = result.layers["kind"]
    size = len(kind_grid)

    # Можно будет вынести в пресет, а пока захардкодим
    rock_density = 0.1  # 10% базовый шанс появления камня

    # Свой собственный, независимый генератор шума для камней
    rock_noise_gen = OpenSimplex((result.seed ^ 0xDEADBEEF) & 0x7FFFFFFF)
    rock_count = 0

    for z in range(size):
        for x in range(size):
            # Камни могут появляться только на земле или песке, и там где еще нет деревьев
            if kind_grid[z][x] in (KIND_GROUND, KIND_SAND):
                is_near_slope = False
                # Проверяем, есть ли рядом склон
                for dz in range(-1, 2):
                    for dx in range(-1, 2):
                        if dx == 0 and dz == 0: continue
                        nx, nz = x + dx, z + dz
                        if 0 <= nx < size and 0 <= nz < size and kind_grid[nz][nx] == KIND_SLOPE:
                            is_near_slope = True
                            break
                    if is_near_slope: break

                # Если рядом есть склон, шанс появления камня сильно повышается
                chance_multiplier = 5.0 if is_near_slope else 1.0

                # Используем простой шум для случайности
                noise_val = (rock_noise_gen.noise2(x * 0.5, z * 0.5) + 1.0) / 2.0

                if noise_val < (rock_density * chance_multiplier):
                    kind_grid[z][x] = KIND_ROCK
                    rock_count += 1

    if rock_count > 0:
        print(f"--- ROCKS: Created {rock_count} rocks for chunk ({result.cx}, {result.cz})")