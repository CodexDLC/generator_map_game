import pygame
import os
from pathlib import Path
import sys

# --- НАСТРОЙКИ ---
ARTIFACTS_ROOT = Path(__file__).parent / "artifacts"
PREVIEW_SIZE = 512
# Максимальный размер итоговой картинки (в пикселях), чтобы избежать падений
MAX_OVERVIEW_DIMENSION = 4096


def create_overview_map(seed: int):
    """
    Находит все preview.png для указанного сида, сшивает их в одну большую,
    безопасно масштабированную карту и сохраняет ее.
    """
    print(f"--- Creating overview map for seed: {seed} ---")

    world_path = ARTIFACTS_ROOT / "world" / "world_location" / str(seed)
    if not world_path.exists():
        print(f"!!! ERROR: No world data found for seed {seed} at path: {world_path}")
        return

    # 1. Находим все чанки и их координаты
    chunk_files = {}
    min_cx, max_cx = float('inf'), float('-inf')
    min_cz, max_cz = float('inf'), float('-inf')

    for chunk_dir in world_path.iterdir():
        if chunk_dir.is_dir():
            try:
                cx_str, cz_str = chunk_dir.name.split('_')
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

    print(f"Found {len(chunk_files)} chunks. Bounds: cx[{min_cx}..{max_cx}], cz[{min_cz}..{max_cz}]")

    # 2. Рассчитываем полный размер карты и коэффициент масштабирования
    map_width_chunks = max_cx - min_cx + 1
    map_height_chunks = max_cz - min_cz + 1
    full_width_px = map_width_chunks * PREVIEW_SIZE
    full_height_px = map_height_chunks * PREVIEW_SIZE

    # --- ГЛАВНОЕ ИСПРАВЛЕНИЕ: БЕЗОПАСНОЕ МАСШТАБИРОВАНИЕ ---
    scale = 1.0
    if full_width_px > MAX_OVERVIEW_DIMENSION or full_height_px > MAX_OVERVIEW_DIMENSION:
        scale = min(MAX_OVERVIEW_DIMENSION / full_width_px, MAX_OVERVIEW_DIMENSION / full_height_px)

    final_map_width = int(full_width_px * scale)
    final_map_height = int(full_height_px * scale)
    final_tile_size = int(PREVIEW_SIZE * scale)
    if final_tile_size < 1: final_tile_size = 1

    print(f"Original map size would be: {full_width_px}x{full_height_px} px. (TOO BIG)")
    print(
        f"Scaling to a safe size: {final_map_width}x{final_map_height} px (each tile will be {final_tile_size}x{final_tile_size}px).")

    # 3. Создаем финальную поверхность и "наклеиваем" на нее масштабированные чанки
    pygame.init()
    overview_surface = pygame.Surface((final_map_width, final_map_height))
    overview_surface.fill((15, 15, 25))

    for i, ((cx, cz), path) in enumerate(chunk_files.items()):
        try:
            chunk_img = pygame.image.load(str(path))
            # Масштабируем каждый чанк перед вставкой
            scaled_chunk = pygame.transform.smoothscale(chunk_img, (final_tile_size, final_tile_size))

            local_x = (cx - min_cx) * final_tile_size
            local_y = (cz - min_cz) * final_tile_size
            overview_surface.blit(scaled_chunk, (local_x, local_y))

            # Добавим прогресс-бар, чтобы было видно, что скрипт работает
            if (i + 1) % 100 == 0:
                print(f"  ...processed {i + 1}/{len(chunk_files)} chunks...")

        except pygame.error as e:
            print(f"!!! WARN: Could not load image for chunk ({cx},{cz}): {e}")

    print("Stitching complete.")

    # 4. Сохраняем результат
    output_path = ARTIFACTS_ROOT / f"_overview_map_{seed}.png"
    try:
        pygame.image.save(overview_surface, str(output_path))
        print(f"\n+++ SUCCESS! Map saved to: {output_path} +++")
    except pygame.error as e:
        print(f"!!! ERROR: Could not save the final map: {e}")

    pygame.quit()


if __name__ == "__main__":
    # Логика для интерактивного ввода seed, как вы и хотели
    try:
        worlds_dir = ARTIFACTS_ROOT / "world" / "world_location"
        available_seeds = sorted([int(p.name) for p in worlds_dir.iterdir() if p.name.isdigit()], reverse=True)

        if not available_seeds:
            print("No generated worlds found in 'artifacts' folder. Run the generator first.")
        else:
            print("Available seeds:", available_seeds)
            seed_str = input(
                f">>> Enter seed to create overview map (or press Enter for latest: {available_seeds[0]}): ")

            if seed_str:
                world_seed = int(seed_str)
            else:
                world_seed = available_seeds[0]

            create_overview_map(world_seed)

    except (ValueError, FileNotFoundError):
        print("Could not find any generated worlds. Run the generator first.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")