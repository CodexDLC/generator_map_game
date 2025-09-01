from __future__ import annotations
from typing import Optional, Tuple, Dict, Any

try:
    from engine.worldgen_core.base.constants import KIND_ROAD
except Exception:
    KIND_ROAD = "road"

Rect = Tuple[int, int, int, int]  # (x0, z0, x1, z1)


def apply_start_gate_shapes(elevation_grid: list[list[float]],
                            preset: Any,
                            cx: int, cz: int) -> Optional[Dict[str, Any]]:
    """
    ДО классификации: формирует стартовую площадку у КРАЯ и стену с «окном».
    Применяется ТОЛЬКО к чанку, указанному в preset.start_gate.only_on.
    Возвращает info для последующей дорисовки дороги (или None).
    """
    cfg = getattr(preset, "start_gate", {}) or {}
    if not cfg.get("enabled", False):
        return None

    only = cfg.get("only_on", {}) or {}
    base_cx = int(only.get("cx", 1))
    base_cz = int(only.get("cz", 0))
    if (cx, cz) != (base_cx, base_cz):
        return None  # строго один чанк

    size = len(elevation_grid)
    if size == 0:
        return None

    elev = getattr(preset, "elevation", {}) or {}
    sea    = float(elev.get("sea_level_m", 5.0))
    step   = float(elev.get("quantization_step_m", 3.0))
    mmax   = float(elev.get("max_height_m", 45.0))
    mlevel = float(elev.get("mountain_level_m", 22.0))

    side  = str(cfg.get("side", "W")).upper()   # ожидаем "W"
    pad_w = max(3, int(cfg.get("pad_w", 12)))
    pad_h = max(3, int(cfg.get("pad_h", 16)))
    inset = 1  # отступ от кромки

    # высота площадки: над водой и не гора, кратная квантованию
    target = sea + step
    if step > 0:
        target = float(int(round(target / step)) * step)
    target = min(target, mlevel - 0.001)

    # прямоугольник площадки (центр по Z, прижат к side)
    z0 = max(inset, (size - pad_h) // 2)
    z1 = min(size - 1 - inset, z0 + pad_h - 1)
    if side == "W":
        x0 = inset
        x1 = min(size - 1 - inset, x0 + pad_w - 1)
    else:  # "E"
        x1 = size - 1 - inset
        x0 = max(inset, x1 - pad_w + 1)

    # --- применяем ---
    cnt_pad = 0
    for z in range(z0, z1 + 1):
        row = elevation_grid[z]
        for x in range(x0, x1 + 1):
            row[x] = target
            cnt_pad += 1

    wall = cfg.get("wall", {}) or {}
    cnt_wall = 0
    if wall.get("enabled", True):
        wside = str(wall.get("side", side)).upper()  # по умолчанию — та же сторона
        thick = max(1, int(wall.get("thick", 3)))

        if wside in ("W", "E"):
            if wside == "W":
                xa0, xa1 = inset, min(size - 1 - inset, inset + thick - 1)
            else:
                xa1 = size - 1 - inset
                xa0 = max(inset, xa1 - thick + 1)

            leave_gap = (wside == side)  # окно под площадку
            for z in range(inset, size - inset):
                if leave_gap and z0 <= z <= z1:
                    continue
                for x in range(xa0, xa1 + 1):
                    elevation_grid[z][x] = mmax
                    cnt_wall += 1

    # ЯВНЫЙ ЛОГ — ты увидишь это в консоли воркера
    print(f"[StartGate] Chunk ({cx},{cz}) side={side} pad=({x0},{z0})..({x1},{z1}) "
          f"target={target:.2f} cells: pad={cnt_pad} wall={cnt_wall}")

    return {
        "rect": (x0, z0, x1, z1),
        "side": side,
        "road_th": max(1, int(cfg.get("road_th", 3))),
        "stats": {"pad_cells": cnt_pad, "wall_cells": cnt_wall}
    }


def paint_start_gate_road(kind_grid: list[list[str]], info: Optional[Dict[str, Any]]) -> None:
    """
    ПОСЛЕ склонов: рисуем дорожную «вставку» в пределах площадки + «розетку» у самой кромки.
    """
    if not info:
        return

    x0, z0, x1, z1 = info["rect"]  # type: ignore
    side = str(info.get("side", "W")).upper()
    th   = int(info.get("road_th", 3)) or 1

    h = len(kind_grid); w = len(kind_grid[0]) if h else 0
    zc   = (z0 + z1) // 2
    half = max(0, th // 2)

    z_from = max(0, zc - half)
    z_to   = min(h - 1, zc + half)
    x_from = max(0, x0)
    x_to   = min(w - 1, x1)

    for z in range(z_from, z_to + 1):
        for x in range(x_from, x_to + 1):
            kind_grid[z][x] = KIND_ROAD

    edge_x = 1 if side == "W" else (w - 2)
    if 0 <= edge_x < w:
        for z in range(z_from, z_to + 1):
            kind_grid[z][edge_x] = KIND_ROAD
