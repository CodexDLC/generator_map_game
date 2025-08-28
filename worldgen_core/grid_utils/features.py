# features.py
from __future__ import annotations
from opensimplex import OpenSimplex
from .core import TILE


def add_water(
    grid: list[list[int]],
    seed: int,
    scale: float,
    *,
    target_density: float = 0.06,
    threshold: float | None = None,
    avoid: set[tuple[int, int]] = frozenset(),
) -> None:
    """
    Кладёт deep-воду (TILE["WATER_DEEP"]) по шуму.
    Если `threshold` не задан, подбирает порог по квантилю так, чтобы доля воды
    среди «пола» была близка к `target_density`. Клетки из `avoid` не трогаются.
    """
    height, width = len(grid), len(grid[0])
    noise = OpenSimplex(seed=seed ^ 0x1A2B3C4D)

    # Собираем значения шума только над клетками пола, не входящими в avoid
    samples: list[float] = []
    coords: list[tuple[int, int]] = []
    for row in range(height):
        for col in range(width):
            if grid[row][col] == TILE["FLOOR"] and (col, row) not in avoid:
                val = (noise.noise2(col / scale, row / scale) + 1.0) * 0.5  # 0..1
                samples.append(val)
                coords.append((col, row))
    if not coords:
        return

    cut = float(threshold) if threshold is not None else sorted(samples)[
        max(0, min(len(samples) - 1, int((1.0 - float(target_density)) * len(samples))))
    ]

    for (cx, cy), val in zip(coords, samples):
        if val > cut:
            grid[cy][cx] = TILE["WATER_DEEP"]


def gen_rooms_map(
    rng,
    w: int,
    h: int,
    rooms_cfg: dict,
    corridor_cfg: dict,
) -> list[list[int]]:
    """
    Генерация карты в режиме 'rooms':
      1) Прямоугольные комнаты с лёгкой «неровностью» контура (jitter).
      2) Соединение комнат L-коридорами, расширенными до заданной ширины.
    Возвращает grid[h][w].
    """
    # Параметры
    count = int(rooms_cfg.get("count", 14))
    rw_min, rw_max = map(int, rooms_cfg.get("w_range", (6, 12)))
    rh_min, rh_max = map(int, rooms_cfg.get("h_range", (5, 11)))
    jitter = float(rooms_cfg.get("jitter", 0.15))     # 0..1
    padding = int(rooms_cfg.get("padding", 1))        # зазор между комнатами
    cor_width = max(1, int(corridor_cfg.get("width", 2)))

    # Инициализация сетки стенами
    grid = [[TILE["WALL"] for _ in range(w)] for _ in range(h)]
    rooms: list[tuple[int, int, int, int]] = []       # (x, y, rw, rh)
    centers: list[tuple[int, int]] = []               # (cx, cy)

    def overlaps(rx: int, ry: int, rw_: int, rh_: int) -> bool:
        """Проверка пересечений с учётом отступа."""
        ax0, ay0, ax1, ay1 = rx - padding, ry - padding, rx + rw_ + padding, ry + rh_ + padding
        for bx, by, bw, bh in rooms:
            bx0, by0, bx1, by1 = bx, by, bx + bw, by + bh
            if not (ax1 <= bx0 or ax0 >= bx1 or ay1 <= by0 or ay0 >= by1):
                return True
        return False

    def dig_room(rx: int, ry: int, rw_: int, rh_: int) -> None:
        """Вырезает комнату и слегка «рябит» контур при jitter > 0."""
        x2, y2 = rx + rw_, ry + rh_
        for yy in range(ry, y2):
            for xx in range(rx, x2):
                grid[yy][xx] = TILE["FLOOR"]
                if jitter > 0.0 and (xx in (rx, x2 - 1) or yy in (ry, y2 - 1)):
                    if rng.random() < jitter and 0 < xx < w - 1 and 0 < yy < h - 1:
                        grid[yy][xx] = TILE["FLOOR"]

    def carve_l_wide(p0: tuple[int, int], p1: tuple[int, int], width_cells: int) -> None:
        """Режет L-коридор между точками и расширяет его на width_cells."""
        (x0, y0), (x1, y1) = p0, p1
        step_x = 1 if x1 >= x0 else -1
        step_y = 1 if y1 >= y0 else -1
        half = max(0, (width_cells - 1) // 2)

        # Горизонтальная часть
        for cx in range(x0, x1 + step_x, step_x):
            for dy in range(-half, half + 1):
                yy = y0 + dy
                if 0 <= cx < w and 0 <= yy < h:
                    grid[yy][cx] = TILE["FLOOR"]
        # Вертикальная часть
        for cy in range(y0, y1 + step_y, step_y):
            for dx in range(-half, half + 1):
                xx = x1 + dx
                if 0 <= xx < w and 0 <= cy < h:
                    grid[cy][xx] = TILE["FLOOR"]

    # Размещение комнат (rejection sampling)
    attempts = count * 12
    while len(rooms) < count and attempts > 0:
        attempts -= 1
        rw_ = rng.randint(rw_min, rw_max)
        rh_ = rng.randint(rh_min, rh_max)
        rx = rng.randint(1, max(1, w - rw_ - 2))
        ry = rng.randint(1, max(1, h - rh_ - 2))
        if overlaps(rx, ry, rw_, rh_):
            continue
        rooms.append((rx, ry, rw_, rh_))
        centers.append((rx + rw_ // 2, ry + rh_ // 2))
        dig_room(rx, ry, rw_, rh_)

    if not centers:
        return grid

    # Рёбра графа соединения: соседние по X + несколько случайных для циклов
    centers.sort(key=lambda p: (p[0], p[1]))
    edges: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for idx in range(len(centers) - 1):
        edges.append((centers[idx], centers[idx + 1]))
    for _ in range(max(1, len(centers) // 4)):
        a_idx = rng.randrange(len(centers))
        b_idx = rng.randrange(len(centers))
        if a_idx != b_idx:
            edges.append((centers[a_idx], centers[b_idx]))

    # Прорезаем коридоры
    for p0, p1 in edges:
        carve_l_wide(p0, p1, cor_width)

    return grid


def carve_room_at(grid: list[list[int]], cx: int, cy: int, w: int = 7, h: int = 7) -> set[tuple[int,int]]:
    """
    Вырезает прямоугольную «комнату» вокруг (cx,cy). Возвращает множество изменённых клеток.
    Границы карты и бордер не ломает.
    """
    H, W = len(grid), len(grid[0])
    x0 = max(1, cx - w // 2)
    x1 = min(W - 2, x0 + w - 1)
    y0 = max(1, cy - h // 2)
    y1 = min(H - 2, y0 + h - 1)
    carved = set()
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            grid[y][x] = TILE["FLOOR"]
            carved.add((x, y))
    return carved