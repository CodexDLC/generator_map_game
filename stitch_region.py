# stitch_region.py
import sys
import pathlib
import numpy as np
from PIL import Image

# --- Конфигурация ---
# Эти значения должны соответствовать вашему проекту
ARTIFACTS_ROOT = pathlib.Path(__file__).resolve().parent / "artifacts"
CHUNK_SIZE = 96  # Размер одного чанка в тайлах
REGION_SIZE = 5  # Размер региона в чанках


def stitch_region(seed: int, scx: int, scz: int):
    """
    Склеивает 25 карт высот (.r16) и превью (.png) одного региона в единые большие файлы.
    (Эта функция остается без изменений)
    """
    print(f"--- Starting stitching for region ({scx}, {scz}) with seed {seed} ---")

    region_world_path = ARTIFACTS_ROOT / "world" / "world_location" / str(seed)
    output_path = ARTIFACTS_ROOT / "stitched_regions" / str(seed)
    output_path.mkdir(parents=True, exist_ok=True)

    final_size_px = REGION_SIZE * CHUNK_SIZE
    final_height_map = np.zeros((final_size_px, final_size_px), dtype=np.uint16)
    final_preview_img = Image.new("RGB", (final_size_px, final_size_px))

    base_cx = scx * REGION_SIZE - (REGION_SIZE // 2)
    base_cz = scz * REGION_SIZE - (REGION_SIZE // 2)

    found_chunks = 0
    for dz in range(REGION_SIZE):
        for dx in range(REGION_SIZE):
            cx = base_cx + dx
            cz = base_cz + dz

            chunk_dir = region_world_path / f"{cx}_{cz}"
            heightmap_path = chunk_dir / "heightmap.r16"
            preview_path = chunk_dir / "preview.png"

            print(f"  Processing chunk ({cx}, {cz})... ", end="")

            if heightmap_path.exists():
                try:
                    chunk_height_data = np.fromfile(str(heightmap_path), dtype=np.uint16).reshape(
                        (CHUNK_SIZE, CHUNK_SIZE))
                    paste_x = dx * CHUNK_SIZE
                    paste_y = dz * CHUNK_SIZE
                    final_height_map[paste_y:paste_y + CHUNK_SIZE, paste_x:paste_x + CHUNK_SIZE] = chunk_height_data

                    chunk_preview_img = Image.open(preview_path)
                    if chunk_preview_img.size != (CHUNK_SIZE, CHUNK_SIZE):
                        chunk_preview_img = chunk_preview_img.resize((CHUNK_SIZE, CHUNK_SIZE))

                    final_preview_img.paste(chunk_preview_img, (paste_x, paste_y))

                    print("OK")
                    found_chunks += 1
                except Exception as e:
                    print(f"ERROR: {e}")
            else:
                print("Not found.")

    if found_chunks == 0:
        print("\nERROR: No chunks found for this region. Did you generate the world first?")
        return

    final_r16_path = output_path / f"region_{scx}_{scz}_heightmap.r16"
    final_png_path = output_path / f"region_{scx}_{scz}_preview.png"

    try:
        final_height_map.tofile(str(final_r16_path))
        print(f"\nSuccessfully saved stitched heightmap to: {final_r16_path}")

        final_preview_img.save(final_png_path)
        print(f"Successfully saved stitched preview to: {final_png_path}")
    except Exception as e:
        print(f"\nCRITICAL ERROR during file save: {e}")


# --- НАЧАЛО ИЗМЕНЕНИЙ: ИНТЕРАКТИВНЫЙ ВЫБОР СИДА ---
if __name__ == "__main__":
    # 1. Находим все папки с сидами
    worlds_path = ARTIFACTS_ROOT / "world" / "world_location"
    if not worlds_path.exists():
        print(f"Error: Directory not found: {worlds_path}")
        sys.exit(1)

    # Получаем список папок, название которых - это число
    available_seeds = sorted([p.name for p in worlds_path.iterdir() if p.is_dir() and p.name.isdigit()])

    if not available_seeds:
        print(f"No generated worlds found in {worlds_path}")
        sys.exit(0)

    # 2. Показываем пользователю меню выбора
    print("\nAvailable worlds (seeds) to stitch:")
    for i, seed_name in enumerate(available_seeds):
        print(f"  {i + 1}: {seed_name}")

    # 3. Запрашиваем ввод
    choice = -1
    while choice < 1 or choice > len(available_seeds):
        try:
            raw_input = input(f"\nEnter the number of the world you want to stitch [1-{len(available_seeds)}]: ")
            choice = int(raw_input)
        except (ValueError, EOFError):
            print("Invalid input. Please enter a number.")
            continue

    # 4. Запускаем склейку для выбранного сида (пока только для региона 0,0)
    selected_seed_str = available_seeds[choice - 1]
    selected_seed = int(selected_seed_str)

    # По умолчанию склеиваем центральный регион (0, 0)
    stitch_region(seed=selected_seed, scx=0, scz=0)
# --- КОНЕЦ ИЗМЕНЕНИЙ ---