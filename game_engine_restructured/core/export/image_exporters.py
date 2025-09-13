# ==============================================================================
# Файл: game_engine_restructured/core/export/image_exporters.py
# Назначение: Функции для генерации изображений (preview.png).
# ==============================================================================
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, List

import numpy as np
from PIL import Image

from ..constants import NAV_ID_TO_KIND, SURFACE_ID_TO_KIND


def _ensure_path_exists(path: str) -> None:
    """Убеждается, что директория для файла существует."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def write_chunk_preview(
        path: str,
        surface_grid,
        nav_grid,
        palette: Dict[str, str],
        verbose: bool = False,
):
    """Рисует превью чанка и сохраняет его в PNG."""
    # --- НАЧАЛО НОВОГО КОДА ДЛЯ ДИАГНОСТИКИ ---
    if verbose:  # Мы используем тот же флаг, что и для лога сохранения файлов
        from collections import Counter
        chunk_coords = Path(path).parent.name
        print(f"  -> [Preview IMG] Stats for chunk {chunk_coords}:")

        # Проверяем, что это numpy-массив, и считаем ID
        if isinstance(surface_grid, np.ndarray):
            counts = Counter(surface_grid.flatten())
            for tile_id, count in sorted(counts.items()):
                tile_name = SURFACE_ID_TO_KIND.get(tile_id, f"Unknown_ID_{tile_id}")
                print(f"     - {tile_name}: {count} pixels")
        else:
            print("     - WARNING: surface_grid is not a NumPy array!")
    # --- КОНЕЦ НОВОГО КОДА ДЛЯ ДИАГНОСТИКИ ---

    if not palette:
        print("[Preview] WARN: preset.export.palette пустая — будут дефолтные цвета.")

    color_map = {
        "water": palette.get("water", "#3A6FD8"),
        "obstacle_prop": palette.get("obstacle_prop", "#444444"),
        "bridge": palette.get("bridge", "#C8A452"),
        "base_dirt": palette.get("base_dirt", "#8B4513"),
        "base_grass": palette.get("base_grass", "#5FAF3A"),
        "base_sand": palette.get("base_sand", "#D8C27A"),
        "base_rock": palette.get("base_rock", "#9AA0A6"),
        "base_road": palette.get("base_road", "#7A5C3A"),
    }
    default_color_hex = color_map["base_dirt"]

    def _ensure_str_grid(
            grid, id2name: Dict[int, str], default_name: str
    ) -> List[List[str]]:
        """
        Гарантирует, что на выходе будет список списков строк,
        безопасно работая с NumPy-массивами.
        """
        # --- НАЧАЛО ИЗМЕНЕНИЙ: Правильная проверка для NumPy ---
        if grid is None or grid.size == 0:
            return []
        # --- КОНЕЦ ИЗМЕНЕНИЙ ---

        # Проверяем, нужно ли конвертировать ID в строки
        # Для numpy-массивов нужно проверять тип элемента, а не всего массива
        if isinstance(grid, np.ndarray) and np.issubdtype(grid.dtype, np.number):
            return [[id2name.get(int(v), default_name) for v in row] for row in grid]

        # Если это уже список списков строк, просто возвращаем его
        if isinstance(grid[0][0], str):
            return grid

        # На случай, если это список списков чисел (старый формат)
        return [[id2name.get(int(v), default_name) for v in row] for row in grid]

    surface_grid_str = _ensure_str_grid(surface_grid, SURFACE_ID_TO_KIND, "base_dirt")
    nav_grid_str = _ensure_str_grid(nav_grid, NAV_ID_TO_KIND, "passable")

    try:
        h = len(surface_grid_str)
        w = len(surface_grid_str[0]) if h else 0
        if w == 0:
            return

        img = Image.new("RGB", (w, h))
        px = img.load()

        for y in range(h):
            for x in range(w):
                nav_kind = nav_grid_str[y][x]
                # Приоритет отрисовки: вода/препятствия важнее текстуры земли
                final_kind = (
                    nav_kind
                    if nav_kind in ("water", "obstacle_prop", "bridge")
                    else surface_grid_str[y][x]
                )
                hex_color = color_map.get(final_kind, default_color_hex).lstrip("#")
                if len(hex_color) == 8: hex_color = hex_color[2:] # Убираем альфа-канал
                r, g, b = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
                px[x, y] = (r, g, b)

        img = img.transpose(Image.FLIP_TOP_BOTTOM).resize(
            (w * 2, h * 2), Image.Resampling.NEAREST
        )

        _ensure_path_exists(path)
        tmp_path = path + ".tmp"
        img.save(tmp_path, format="PNG")
        os.replace(tmp_path, path)

        if verbose:
            print(f"--- EXPORT: Preview image saved: {path}")

    except Exception as e:
        import traceback
        print(f"[Preview] CRITICAL ERROR: {e}")
        traceback.print_exc()