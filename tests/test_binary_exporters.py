# ==============================================================================
# Файл: tests/test_binary_exporters.py
# Назначение: Юнит-тесты для функций сохранения бинарных данных.
# ==============================================================================
import unittest
import numpy as np
import tempfile
import os
import struct

# Добавляем путь к проекту, чтобы можно было импортировать модули движка
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from game_engine_restructured.core.export.binary_exporters import (
    _pack_control_data,
    write_control_map_r32,
)


class TestBinaryExporters(unittest.TestCase):
    """Набор тестов для проверки корректности упаковки и сохранения данных."""

    def test_pack_control_data(self):
        """Тестирует побитовую упаковку данных в 32-битное число."""
        print("\n[TEST] Running test_pack_control_data...")

        # Тестовый случай 1: Песок (ID 2), проходимый
        val1 = _pack_control_data(base_id=2, overlay_id=0, blend=0, nav=True)
        self.assertEqual((val1 >> 27) & 0x1F, 2, "base_id for sand failed")
        self.assertEqual((val1 >> 3) & 0x1, 1, "nav for sand failed")

        # Тестовый случай 2: Вода (ID 6), непроходимая (nav=False)
        val2 = _pack_control_data(base_id=6, overlay_id=0, blend=0, nav=False)
        self.assertEqual((val2 >> 27) & 0x1F, 6, "base_id for water failed")
        self.assertEqual((val2 >> 3) & 0x1, 0, "nav for water failed")

        # Тестовый случай 3: Полный набор с overlay и blend
        val3 = _pack_control_data(base_id=1, overlay_id=11, blend=255, nav=True)
        self.assertEqual((val3 >> 27) & 0x1F, 1, "base_id with overlay failed")
        self.assertEqual((val3 >> 22) & 0x1F, 11, "overlay_id not preserved")
        self.assertEqual((val3 >> 14) & 0xFF, 255, "blend not preserved")
        self.assertEqual((val3 >> 3) & 0x1, 1, "nav with overlay failed")

        print("[TEST] test_pack_control_data: OK")

    def test_write_and_read_control_map_r32(self):
        """
        Интеграционный тест: записывает control.r32 в временный файл,
        читает его и проверяет, что данные соответствуют исходным.
        """
        print("\n[TEST] Running test_write_and_read_control_map_r32...")

        # 1. Создаем моковые (тестовые) данные
        h, w = 4, 4
        surface_grid = np.array([
            [0, 1, 2, 3],
            [4, 5, 6, 7],
            [8, 9, 10, 11],
            [12, 0, 0, 0]
        ], dtype=np.uint8)

        nav_grid = np.array([
            [0, 0, 0, 0],  # passable
            [1, 1, 1, 1],  # obstacle
            [2, 2, 2, 2],  # water
            [7, 7, 7, 7]  # bridge
        ], dtype=np.uint8)

        overlay_grid = np.zeros((h, w), dtype=np.uint8)
        overlay_grid[0, 1] = 11  # Добавляем один overlay для теста

        # 2. Используем временный файл, чтобы не мусорить в проекте
        with tempfile.NamedTemporaryFile(delete=False, suffix=".r32") as tmp_file:
            filepath = tmp_file.name

        try:
            # 3. Вызываем тестируемую функцию
            write_control_map_r32(filepath, surface_grid, nav_grid, overlay_grid)

            # 4. Читаем сырые байты из созданного файла
            with open(filepath, 'rb') as f:
                raw_bytes = f.read()

            self.assertEqual(len(raw_bytes), h * w * 4)  # Проверяем размер файла

            # 5. Распаковываем байты обратно в числа
            unpacked_data = struct.unpack(f'<{h * w}I', raw_bytes)

            # 6. Проверяем ключевые пиксели
            # Пиксель (1, 0) - трава (id=1), проходимый (nav=True)
            px_1_0 = unpacked_data[1]
            self.assertEqual((px_1_0 >> 27) & 0x1F, 1)  # base_id
            self.assertEqual((px_1_0 >> 22) & 0x1F, 11)  # overlay_id
            self.assertEqual((px_1_0 >> 3) & 0x1, 1)  # nav

            # Пиксель (2, 1) - вода (id=5), непроходимый (nav=False)
            px_2_1 = unpacked_data[4 + 1]
            self.assertEqual((px_2_1 >> 27) & 0x1F, 5)  # base_id
            self.assertEqual((px_2_1 >> 3) & 0x1, 0)  # nav (препятствие)

            print("[TEST] test_write_and_read_control_map_r32: OK")

        finally:
            # Гарантированно удаляем временный файл
            if os.path.exists(filepath):
                os.remove(filepath)


if __name__ == '__main__':
    unittest.main()