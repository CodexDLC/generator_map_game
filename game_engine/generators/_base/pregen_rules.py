# game_engine/generators/_base/pregen_rules.py
from __future__ import annotations

import math
from typing import Any, Optional, Tuple, List
import random

from ...core.constants import KIND_WATER

DEBUG_PREG = True
FillDecision = Tuple[str, float]  # (kind, height)


def _pre(preset: Any) -> dict:
    return getattr(preset, "pre_rules", {}) or {}


def early_fill_decision(cx: int, cz: int, size: int, preset: Any, seed: int) -> Optional[FillDecision]:
    """
    Правило океана: все чанки с cz >= cz_min_ocean -> вода.
    Исключение: cz == 0 (нужно для рисования берега).
    """
    elev = getattr(preset, "elevation", {}) or {}
    sea = float(elev.get("sea_level_m", 20.0))
    water_h = sea - 0.1

    ocean = _pre(preset).get("south_ocean", {}) or {}
    cz_min = int(ocean.get("cz_min_ocean", 1))

    if DEBUG_PREG:
        print(f"[PREG] early_fill? cx={cx} cz={cz} cz_min_ocean={cz_min}", flush=True)

    if cz >= cz_min and cz != 0:
        if DEBUG_PREG:
            print(f"[PREG] early_fill=OCEAN cx={cx} cz={cz}", flush=True)
        return (KIND_WATER, water_h)

    if DEBUG_PREG:
        print(f"[PREG] early_fill=NO cx={cx} cz={cz}", flush=True)
    return None


def modify_elevation_inplace(elev_grid: List[List[float]],
                             cx: int, cz: int, size: int, preset: Any, seed: int) -> None:
    """
    Создает плавный переход к океану на южной стороне чанков с cz=0.
    Вместо рваного берега создается гладкий склон (пляж).
    """
    # Это правило работает только для линии чанков cz=0
    if cz != 0:
        return

    # Получаем настройки
    pre = getattr(preset, "pre_rules", {}) or {}
    cfg = pre.get("cz0_coast", {}) or {}

    # Определяем зону перехода (например, южная треть чанка)
    transition_depth_tiles = max(1, int(cfg.get("depth_max_tiles", size // 3)))

    elev_cfg = getattr(preset, "elevation", {}) or {}
    sea_level = float(elev_cfg.get("sea_level_m", 20.0))
    ocean_h = sea_level - 0.1  # Высота океана в чанках cz=1

    # Координата Z, с которой начинается плавный спуск
    start_z = size - transition_depth_tiles

    # Проходим по всем клеткам в зоне перехода
    for z in range(start_z, size):
        # Коэффициент перехода от 0 (начало спуска) до 1 (полный океан)
        # Используем math.sin для более плавного, нелинейного изгиба пляжа
        ratio = (z - start_z) / (transition_depth_tiles - 1)
        smooth_ratio = math.sin(ratio * math.pi / 2)

        for x in range(size):
            original_h = elev_grid[z][x]

            # Интерполируем высоту от оригинальной до высоты океана
            # Чем ближе к южному краю (ratio -> 1), тем ближе высота к ocean_h
            new_h = original_h * (1 - smooth_ratio) + ocean_h * smooth_ratio

            # Если новая высота ниже уровня моря, это точно вода
            if new_h < sea_level:
                elev_grid[z][x] = new_h
            # Если она чуть выше, делаем ее равной уровню моря, чтобы избежать
            # появления одиноких "холмиков" на пляже
            elif new_h < sea_level + 0.5:  # Небольшой порог
                elev_grid[z][x] = sea_level
            # В остальных случаях оставляем как есть, чтобы не трогать высокие горы
            # которые могут выходить к воде
