# ==============================================================================
# Файл: debug_control_map.py
# Назначение: Утилита для чтения и анализа бинарного файла control.r32.
# ==============================================================================
import sys
import struct
from collections import Counter

# Скопируем сюда ID текстур, чтобы скрипт был независимым
SURFACE_ID_TO_KIND = {
    0: "base_dirt", 1: "base_grass", 2: "base_sand", 3: "base_rock",
    4: "base_road", 5: "base_cracked", 6: "base_waterbed", 7: "overlay_snow",
    8: "overlay_leafs_green", 9: "overlay_leafs_autumn", 10: "overlay_flowers",
    11: "overlay_dirt_grass", 12: "overlay_desert_stones",
}


def decode_pixel(pixel_data: int) -> dict:
    """Декодирует одно 32-битное число в его компоненты."""
    base_id = (pixel_data >> 27) & 0x1F
    overlay_id = (pixel_data >> 22) & 0x1F
    blend = (pixel_data >> 14) & 0xFF
    nav = (pixel_data >> 3) & 0x01
    return {
        "base_id": base_id,
        "overlay_id": overlay_id,
        "blend": blend,
        "nav": bool(nav)
    }


def analyze_control_map(file_path: str):
    """Главная функция для анализа файла."""
    try:
        with open(file_path, "rb") as f:
            raw_bytes = f.read()
    except FileNotFoundError:
        print(f"!!! ОШИБКА: Файл не найден по пути: {file_path}")
        return
    except Exception as e:
        print(f"!!! ОШИБКА: Не удалось прочитать файл. {e}")
        return

    if not raw_bytes:
        print("--- Файл пустой.")
        return

    # Каждый пиксель - это 4 байта (32-битное беззнаковое целое)
    # '<' означает little-endian порядок байт, 'I' - unsigned int
    num_pixels = len(raw_bytes) // 4
    try:
        pixels = struct.unpack(f'<{num_pixels}I', raw_bytes)
    except struct.error as e:
        print(f"!!! ОШИБКА: Неверный размер файла. Он должен быть кратен 4 байтам. {e}")
        return

    print(f"\n--- Анализ файла: {file_path} ---")
    print(f"Всего пикселей: {num_pixels} (размер чанка {int(num_pixels ** 0.5)}x{int(num_pixels ** 0.5)})")

    # Считаем, сколько раз встречается каждый ID базовой текстуры
    base_id_counts = Counter(decode_pixel(p)["base_id"] for p in pixels)

    if not base_id_counts:
        print("--- Не найдено ни одного пикселя для анализа.")
        return

    print("\n--- Статистика по базовым текстурам (Base ID): ---")
    total_found = 0
    for base_id, count in sorted(base_id_counts.items()):
        texture_name = SURFACE_ID_TO_KIND.get(base_id, f"НЕИЗВЕСТНЫЙ_ID_{base_id}")
        print(f"  - ID {base_id} ({texture_name}):\t{count} пикселей")
        total_found += count

    print(f"\nПроверка: Найдено {total_found} из {num_pixels} пикселей.")
    print("--- Анализ завершен. ---\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python debug_control_map.py <путь_к_файлу_control.r32>")
        # Пример для удобства
        print("\nПример:")
        print("python debug_control_map.py artifacts/world/world_location/25/-5_-5/control.r32")
    else:
        analyze_control_map(sys.argv[1])