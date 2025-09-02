# game_engine/world_structure/regions.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Tuple


# Используем dataclass для удобного хранения данных о регионе.
# В будущем мы добавим сюда biome, difficulty и т.д.
@dataclass
class Region:
    """Хранит все метаданные для одного региона (суперчанка)."""
    scx: int
    scz: int
    # Пока что других полей нет, но они появятся здесь
    biome_type: str = "placeholder_biome"
    difficulty: float = 1.0


class RegionManager:
    """
    Главный класс для управления сеткой регионов (суперчанков).
    Отвечает за вычисление координат и генерацию/загрузку данных региона.
    """

    def __init__(self, world_seed: int, region_size: int = 5):
        if region_size % 2 == 0:
            raise ValueError("Размер региона должен быть нечетным (3, 5, 7...), чтобы иметь центр.")

        self.world_seed = world_seed
        self.region_size = region_size
        self.cache: dict[Tuple[int, int], Region] = {}

    def get_region_coords_from_chunk_coords(self, cx: int, cz: int) -> Tuple[int, int]:
        """
        Главная функция: определяет, к какому региону принадлежит чанк.
        Использует целочисленное деление.
        """
        # Эта формула корректно работает и для отрицательных координат
        scx = cx // self.region_size
        scz = cz // self.region_size
        return scx, scz

    def get_chunk_coords_in_region(self, cx: int, cz: int) -> Tuple[int, int]:
        """Возвращает локальные координаты чанка внутри его региона (от 0 до 4)."""
        local_cx = cx % self.region_size
        local_cz = cz % self.region_size
        return local_cx, local_cz

    def get_region_data(self, scx: int, scz: int) -> Region:
        """
        Получает данные для региона.
        Если данных нет в кэше, генерирует их.
        """
        if (scx, scz) in self.cache:
            return self.cache[(scx, scz)]

        # --- ЗАГЛУШКА: Логика генерации данных региона ---
        # Здесь в будущем будет сложная логика, определяющая биом и сложность
        # в зависимости от координат региона (scx, scz) и сида мира.
        # Например, здесь будет реализация вашего "веера" сложности.

        # Пока что просто создаем регион-пустышку
        print(f"[RegionManager] Generating data for new region ({scx}, {scz})...")
        new_region = Region(scx=scx, scz=scz)

        # Кэшируем и возвращаем результат
        self.cache[(scx, scz)] = new_region
        return new_region


