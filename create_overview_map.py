import pygame
import os
import math
from pathlib import Path
import sys

# --- НАСТРОЙКИ ---
ARTIFACTS_ROOT = Path(__file__).parent / "artifacts"
PREVIEW_SIZE = 256  # Соответствует chunk_px=256
MAX_OVERVIEW_DIMENSION = 4096
HEX_ORIENTATION = "pointy-top"  # Из hex.py
EDGE_M = 0.63  # Значение из region.py
METERS_PER_PIXEL = 1.0  # Уточните из пресета
SQRT3 = math.sqrt(3.0)

def create_overview_map(seed: int):
    """
    Находит все preview.png для указанного сида, сшивает их в одну большую,
    безопасно масштабированную карту с учетом pointy-top HEX-сетки и сохраняет.
    """
    print(f"--- Creating overview map for seed: {seed} (HEX: {HEX_ORIENTATION}) ---")

    world_path = ARTIFACTS_ROOT / "world" / "world_location" / str(seed)
    if not world_path.exists():
        print(f"!!! ERROR: No world data found for seed {seed} at path: {world_path}")
        return

    # 1. Находим все чанки и их координаты (axial: cx, cz)
    chunk_files = {}
    min_cx, max_cx = float("inf"), float("-inf")
    min_cz, max_cz = float("inf"), float("-inf")

    for chunk_dir in world_path.iterdir():
        if chunk_dir.is_dir():
            try:
                cx_str, cz_str = chunk_dir.name.split("_")
                cx, cz = int(cx_str), int(cz_str)
                preview_path = chunk_dir / "preview.png"
                if preview_path.exists():
                    chunk_files[(cx, cz)] = preview_path
                    min_cx, max_cx = min(min_cx, cx), max(max_cx, cx)
                    min_cz, max_cz = min(min_cz, cz), max(max_cz, cz)
            except ValueError:
                continue

    if not chunk_files:
        print("!!! ERROR: No valid chunk previews found to create a map.")
        return

    print(
        f"Found {len(chunk_files)} chunks. Bounds: cx[{min_cx}..{max_cx}], cz[{min_cz}..{max_cz}]"
    )

    # 2. Рассчитываем размер карты с HEX-геометрией (pointy-top из hex.py)
    chunk_size_m = PREVIEW_SIZE * METERS_PER_PIXEL  # Физический размер чанка
    hex_x_step = SQRT3 * EDGE_M / METERS_PER_PIXEL  # Горизонтальный шаг в пикселях
    hex_y_step = 1.5 * EDGE_M / METERS_PER_PIXEL    # Вертикальный шаг в пикселях
    # Нормируем шаги к размеру чанка
    px_x_step = (hex_x_step / chunk_size_m) * PREVIEW_SIZE
    px_y_step = (hex_y_step / chunk_size_m) * PREVIEW_SIZE
    px_offset_y = px_y_step / 2  # Смещение для нечетных CX

    num_cols = max_cx - min_cx + 1
    num_rows = max_cz - min_cz + 1
    full_width_px = num_cols * PREVIEW_SIZE
    full_height_px = num_rows * PREVIEW_SIZE * (hex_y_step / hex_x_step)  # Корректировка по Y

    # Безопасное масштабирование
    scale = 1.0
    if full_width_px > MAX_OVERVIEW_DIMENSION or full_height_px > MAX_OVERVIEW_DIMENSION:
        scale = min(
            MAX_OVERVIEW_DIMENSION / full_width_px,
            MAX_OVERVIEW_DIMENSION / full_height_px,
        )

    final_map_width = int(full_width_px * scale)
    final_map_height = int(full_height_px * scale)
    final_tile_size = int(PREVIEW_SIZE * scale)
    final_x_step = int(px_x_step * scale)
    final_y_step = int(px_y_step * scale)
    final_offset_y = int(px_offset_y * scale)
    if final_tile_size < 1:
        final_tile_size = 1

    print(f"Original HEX map size: {full_width_px}x{full_height_px} px.")
    print(
        f"Scaling to: {final_map_width}x{final_map_height} px (tile={final_tile_size}px, x_step={final_x_step}px, y_step={final_y_step}px, y_offset={final_offset_y}px)."
    )

    # 3. Создаем поверхность и размещаем чанки
    pygame.init()
    overview_surface = pygame.Surface((final_map_width, final_map_height))
    overview_surface.fill((15, 15, 25))  # Темный фон

    for i, ((cx, cz), path) in enumerate(chunk_files.items()):
        try:
            chunk_img = pygame.image.load(str(path))
            if scale > 0.5:
                scaled_chunk = pygame.transform.smoothscale(chunk_img, (final_tile_size, final_tile_size))
            else:
                scaled_chunk = pygame.transform.scale(chunk_img, (final_tile_size, final_tile_size))

            # Позиция с учетом pointy-top: смещение по Y для нечетных CX
            rel_cx = cx - min_cx
            rel_cz = cz - min_cz
            local_x = rel_cx * final_tile_size
            local_y = rel_cz * final_y_step
            if rel_cx % 2 != 0:  # Нечетный CX -> смещение по Y
                local_y += final_offset_y

            overview_surface.blit(scaled_chunk, (local_x, local_y))
            print(f"Placing chunk ({cx},{cz}) at ({local_x},{local_y}) with size {final_tile_size}x{final_tile_size}")

            if (i + 1) % 5 == 0 or i == len(chunk_files) - 1:
                print(f"  ...processed {i + 1}/{len(chunk_files)} chunks...")

        except pygame.error as e:
            print(f"!!! WARN: Could not load image for chunk ({cx},{cz}): {e}")

    print("Stitching complete.")

    # 4. Сохраняем результат
    output_path = ARTIFACTS_ROOT / f"_overview_map_{seed}_hex.png"
    try:
        pygame.image.save(overview_surface, str(output_path))
        print(f"\n+++ SUCCESS! HEX map saved to: {output_path} +++")
    except pygame.error as e:
        print(f"!!! ERROR: Could not save the final map: {e}")

    pygame.quit()


if __name__ == "__main__":
    try:
        worlds_dir = ARTIFACTS_ROOT / "world" / "world_location"
        available_seeds = sorted(
            [int(p.name) for p in worlds_dir.iterdir() if p.name.isdigit()],
            reverse=True,
        )

        if not available_seeds:
            print(
                "No generated worlds found in 'artifacts' folder. Run the generator first."
            )
        else:
            print("Available seeds:", available_seeds)
            seed_str = input(
                f">>> Enter seed to create overview map (or press Enter for latest: {available_seeds[0]}): "
            )

            if seed_str:
                world_seed = int(seed_str)
            else:
                world_seed = available_seeds[0]

            create_overview_map(world_seed)

    except (ValueError, FileNotFoundError):
        print("Could not find any generated worlds. Run the generator first.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")