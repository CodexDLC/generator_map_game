# debug_control_map.py
import numpy as np
import sys
import os

# Словарь ID, который соответствует вашему файлу constants.py
# Мы используем его для расшифровки
ID_TO_SURFACE_KIND = {
    0: "ground",
    1: "sand",
    2: "road",
    3: "slope",
    4: "forest_ground",
    5: "void",
}

def analyze_control_map(file_path):
    """Читает и расшифровывает файл control.r32."""
    if not os.path.exists(file_path):
        print(f"ОШИБКА: Файл не найден по пути: {file_path}")
        return

    try:
        # Читаем все байты из файла
        with open(file_path, 'rb') as f:
            raw_bytes = f.read()

        # Преобразуем байты в массив 32-битных чисел
        # NumPy сам определит правильный порядок байтов для вашей системы
        data = np.frombuffer(raw_bytes, dtype=np.uint32)

        # Определяем размер чанка (например, 128x128 или 256x256)
        side = int(np.sqrt(len(data)))
        if side * side != len(data):
            print(f"ОШИБКА: Некорректный размер файла. Не является квадратом.")
            return

        print(f"--- Анализ файла {os.path.basename(file_path)} ({side}x{side}) ---")

        # Расшифровываем данные для каждого пикселя
        material_ids = []
        for val in data:
            # Чтобы получить ID материала, нам нужно взять только первые 5 бит
            material_id = val & 0x1F  # 0x1F это битовая маска для 5 бит (00011111)
            material_ids.append(material_id)

        # Переводим массив в 2D-сетку
        grid = np.array(material_ids).reshape((side, side))

        # Выводим небольшой участок (16x16) из центра карты для наглядности
        print("\nРасшифрованные ID материалов (участок 16x16 из центра):")
        start = side // 2 - 8
        end = side // 2 + 8
        print(grid[start:end, start:end])

        # Считаем, сколько раз встречается каждый ID
        unique, counts = np.unique(grid, return_counts=True)
        print("\nСтатистика по всем ID материалов в чанке:")
        for i, uid in enumerate(unique):
            kind_name = ID_TO_SURFACE_KIND.get(uid, "НЕИЗВЕСТНЫЙ ID")
            print(f"  ID {uid} ({kind_name}):\tвстречается {counts[i]} раз")

    except Exception as e:
        print(f"Произошла критическая ошибка: {e}")


if __name__ == "__main__":
    # Проверяем, был ли передан путь к файлу
    if len(sys.argv) > 1:
        path_to_check = sys.argv[1]
        analyze_control_map(path_to_check)
    else:
        print("\nПожалуйста, укажите путь к файлу control.r32.")
        print(r"Пример: python debug_control_map.py artifacts\world\world_location\25\0_0\control.r32")