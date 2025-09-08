from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Iterable, List, Tuple

SQRT3 = math.sqrt(3.0)

@dataclass(frozen=True)
class HexGridSpec:
    """Спецификация hex-сетки внутри одного чанка."""
    edge_m: float              # длина ребра гекса в метрах (a)
    meters_per_pixel: float    # масштаб рельефа (м/пиксель) в heightmap
    chunk_px: int              # ширина/высота heightmap в пикселях (обычно 256)
    orientation: str = "pointy-top"  # других не поддерживаем в этом проекте

    @property
    def chunk_size_m(self) -> float:
        """Физический размер стороны чанка в метрах."""
        return self.chunk_px * self.meters_per_pixel

    @property
    def dx(self) -> float:
        """Горизонтальный шаг между центрами гексов (pointy-top)."""
        return SQRT3 * self.edge_m

    @property
    def dy(self) -> float:
        """Вертикальный шаг между рядами центров (pointy-top)."""
        return 1.5 * self.edge_m

    def dims_for_chunk(self) -> Tuple[int, int]:
        """Сколько колонок/рядов гексов поместится в чанк по физразмеру."""
        cols = int(round(self.chunk_size_m / self.dx))
        rows = int(round(self.chunk_size_m / self.dy))
        return cols, rows

    # --- Axial <-> world (x,z) ---

    def axial_to_world(self, q: int, r: int) -> Tuple[float, float]:
        """
        Центр гекса (q,r) в мировых координатах XZ внутри чанка [0..L].
        Формулы для pointy-top.
        """
        x = SQRT3 * self.edge_m * (q + r / 2.0)
        z = 1.5 * self.edge_m * r
        return x, z

    def world_to_axial(self, x: float, z: float) -> Tuple[int, int]:
        """
        Обратное преобразование (приближённое) + cube-round.
        Возвращает ближайший гекс (q,r) внутри чанка.
        """
        # перевод в «фракционные» axial
        qf = (SQRT3 / 3.0 * x - (1.0 / 3.0) * z) / self.edge_m
        rf = ((2.0 / 3.0) * z) / self.edge_m

        # axial -> cube
        xf = qf
        zf = rf
        yf = -xf - zf

        # округление кубических координат
        rx = round(xf); ry = round(yf); rz = round(zf)
        dx = abs(rx - xf); dy = abs(ry - yf); dz = abs(rz - zf)
        if dx > dy and dx > dz:
            rx = -ry - rz
        elif dy > dz:
            ry = -rx - rz
        else:
            rz = -rx - ry

        q = int(rx)
        r = int(rz)
        return q, r

    # --- Соседи и расстояния ---

    @staticmethod
    def neighbors(q: int, r: int) -> List[Tuple[int, int]]:
        """Шесть соседей (E, NE, NW, W, SW, SE) в axial."""
        return [
            (q + 1, r + 0), (q + 1, r - 1), (q + 0, r - 1),
            (q - 1, r + 0), (q - 1, r + 1), (q + 0, r + 1),
        ]

    @staticmethod
    def cube_distance(aq: int, ar: int, bq: int, br: int) -> int:
        """Расстояние между гексами (в рёбрах) через cube-метрику."""
        ax, az = aq, ar
        ay = -ax - az
        bx, bz = bq, br
        by = -bx - bz
        return int((abs(ax - bx) + abs(ay - by) + abs(az - bz)) / 2)

    # --- Привязка к пиксельной карте высот ---

    def world_to_px(self, x: float, z: float) -> Tuple[float, float]:
        """
        Перевод местоположения в метрах в координаты пиксельной карты (float).
        0..chunk_px-1 по каждой оси.
        """
        L = self.chunk_size_m
        u = x / self.meters_per_pixel
        v = z / self.meters_per_pixel
        # клауза для численной устойчивости
        u = max(0.0, min(u, self.chunk_px - 1.0001))
        v = max(0.0, min(v, self.chunk_px - 1.0001))
        return u, v
