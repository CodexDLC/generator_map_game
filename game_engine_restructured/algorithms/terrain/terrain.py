# Файл: game_engine_restructured/algorithms/terrain/terrain.py
from __future__ import annotations
from typing import Any, Dict
import numpy as np

# --- НАШИ НОВЫЕ ИНСТРУМЕНТЫ ---
# Импортируем модули с нашими нодами
from .nodes import noise, blending, effects

# --- РЕЕСТР НОД ---
# Этот словарь связывает строковое имя "type" из JSON-конфига
# с конкретной функцией-нодой в нашем коде.
NODE_REGISTRY = {
    "noise": noise.generate_layer,
    "masked_stamp": blending.apply_masked_stamp,
    "masked_noise": blending.apply_masked_noise,
    "walker_stampede": blending.apply_walker_stampede,
    "terracing": effects.apply_terracing,
    "selective_smoothing": effects.apply_selective_smoothing
}


def _print_range(tag: str, arr: np.ndarray) -> None:
    """Вспомогательная функция для диагностики."""
    if arr.size == 0: return
    mn, mx = float(np.min(arr)), float(np.max(arr))
    print(f"  -> [DIAGNOSTIC] Диапазон '{tag}': min={mn:<8.2f} max={mx:<8.2f} delta={mx - mn:.2f}")


def generate_elevation_region(
        seed: int, scx: int, scz: int, region_size_chunks: int, chunk_size: int, preset: Any, scratch_buffers: dict,
) -> np.ndarray:
    """
    Главная функция-оркестратор. Генерирует карту высот, выполняя шаги из конвейера.
    """
    # --- ШАГ 1: Подготовка координат (без изменений) ---
    cfg = getattr(preset, "elevation", {})
    cell_size = float(getattr(preset, "cell_size", 1.0))
    ext_size = (region_size_chunks + 2) * chunk_size
    base_cx = scx * region_size_chunks - 1
    base_cz = scz * region_size_chunks - 1
    gx0_px = base_cx * chunk_size
    gz0_px = base_cz * chunk_size

    px_coords_x = np.arange(ext_size, dtype=np.float32) + gx0_px
    px_coords_z = np.arange(ext_size, dtype=np.float32) + gz0_px
    x_coords, z_coords = np.meshgrid(px_coords_x, px_coords_z)

    # --- ШАГ 2: Инициализация конвейера ---
    # Получаем список операций из JSON-конфига
    pipeline_steps = cfg.get("pipeline", [])
    if not pipeline_steps:
        print("!!! [Terrain] CRITICAL ERROR: Конвейер 'pipeline' не найден или пуст в конфиге. Генерация остановлена.")
        return np.zeros_like(x_coords)

    print("-> [Terrain] Запуск динамического конвейера...")

    # Создаем "контекст" - словарь, который передается от ноды к ноде.
    # Он содержит все текущие данные сцены.
    context = {
        "main_heightmap": np.zeros_like(x_coords, dtype=np.float32),
        "x_coords": x_coords,
        "z_coords": z_coords,
        "cell_size": cell_size,
        "seed": seed
    }

    # --- ШАГ 3: Главный цикл выполнения конвейера ---
    for i, step_cfg in enumerate(pipeline_steps):
        if not step_cfg.get("enabled", True):
            continue

        node_type = step_cfg.get("type")
        node_id = step_cfg.get("id", f"unnamed_{node_type}")

        if not node_type:
            print(f"!!! [Terrain] WARNING: Шаг {i + 1} пропущен, отсутствует 'type'.")
            continue

        node_func = NODE_REGISTRY.get(node_type)
        if not node_func:
            print(f"!!! [Terrain] WARNING: Нода типа '{node_type}' (id: {node_id}) не найдена в реестре. Шаг пропущен.")
            continue

        print(f"  -> Шаг {i + 1}/{len(pipeline_steps)}: Выполнение ноды '{node_id}' (тип: {node_type})...")

        # Вызываем функцию-ноду, передавая ей ее параметры и ВЕСЬ контекст.
        # Нода возвращает обновленный контекст, который пойдет на вход следующей ноде.
        try:
            context = node_func(params=step_cfg.get("params", {}), context=context)
            # --- ДОБАВЬТЕ ЭТУ СТРОКУ ---
            _print_range(f"After '{node_id}'", context["main_heightmap"])

        except Exception as e:
            print(f"!!! [Terrain] CRITICAL ERROR при выполнении ноды '{node_id}': {e}")
            # Здесь можно решить, останавливать ли всю генерацию или продолжать
            # return np.zeros_like(x_coords) # Остановка
            continue  # Продолжение

    # --- ШАГ 4: Завершение и пост-эффекты ---
    height_grid = context["main_heightmap"]

    # Применяем финальные общие параметры
    height_grid += float(cfg.get("base_height_m", 0.0))

    _print_range("Final Heightmap", height_grid)

    return height_grid.copy()