from typing import List, Tuple

from engine.worldgen_core.base.constants import KIND_GROUND, KIND_OBSTACLE, KIND_WATER
from engine.worldgen_core.base.types import GenResult

from engine.worldgen_core.grid_alg.topology.border import apply_border_ring


def _step_cost(kind: List[List[str]],
               height_grid: List[List[float]],
               x: int, z: int, nx: int, nz: int) -> float:
    """
    Рассчитывает стоимость перехода между двумя ячейками.
    Учитывает тип ландшафта и изменение высоты.
    """
    type_cost = {
        KIND_GROUND: 1.0,
        KIND_OBSTACLE: 100.0,  # Препятствия почти непроходимы
        KIND_WATER: 25.0,     # По воде идти дорого
    }.get(kind[nz][nx], 1.0)

    # Штраф за подъем/спуск
    height_diff = abs(height_grid[z][x] - height_grid[nz][nx])
    slope_penalty = height_diff * 50.0 # Коэффициент можно настроить

    return type_cost + slope_penalty


def dijkstra_path(kind: List[List[str]],
                  height_grid: List[List[float]],
                  start: Tuple[int, int], goal: Tuple[int, int]) -> List[Tuple[int, int]]:
    import heapq
    h = len(kind)
    w = len(kind[0]) if h else 0
    sx, sz = start
    gx, gz = goal

    dist = [[float('inf') for _ in range(w)] for _ in range(h)]
    prev: List[List[Tuple[int, int] | None]] = [[None for _ in range(w)] for _ in range(h)]
    pq: List[Tuple[float, int, int]] = []

    dist[sz][sx] = 0
    heapq.heappush(pq, (0.0, sx, sz))

    while pq:
        d, x, z = heapq.heappop(pq)
        if (x, z) == (gx, gz): break
        if d > dist[z][x]: continue

        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = x + dx, z + dz
            if 0 <= nx < w and 0 <= nz < h:
                # Стоимость шага теперь зависит от рельефа
                cost = _step_cost(kind, height_grid, x, z, nx, nz)
                if dist[z][x] + cost < dist[nz][nx]:
                    dist[nz][nx] = dist[z][x] + cost
                    prev[nz][nx] = (x, z)
                    heapq.heappush(pq, (dist[nz][nx], nx, nz))

    path: List[Tuple[int, int]] = []
    curr = goal
    # <<< ИЗМЕНЕНА ЛОГИКА ВОЗВРАТА >>>
    if prev[curr[1]][curr[0]] is None and curr != start:
        return None  # Путь не найден

    while curr is not None:
        path.append(curr)
        if curr == start: break
        curr = prev[curr[1]][curr[0]]

    path.reverse()
    return path

def carve_path_emergency(kind: List[List[str]], path: List[Tuple[int,int]]) -> None:
    """Силой пробивает туннель по координатам пути, меняя все на землю."""
    if not path: return
    for x, z in path:
        # Просто меняем тайл на землю. Можно усложнить, добавив стены.
        kind[z][x] = KIND_GROUND

def find_path_network(kind: List[List[str]],
                      height_grid: List[List[float]],
                      points: List[Tuple[int, int]]) -> List[List[Tuple[int, int]] | None]:
    """
    Находит сеть путей, соединяющих все точки, но не изменяет ландшафт.
    Возвращает список путей. Путь может быть None, если он не найден.
    """
    if len(points) < 2: return []
    paths: List[List[Tuple[int, int]] | None] = []
    center_point = points[0]
    for other_point in points[1:]:
        path = dijkstra_path(kind, height_grid, center_point, other_point)
        paths.append(path)
    return paths

def add_border(self, result: GenResult):
    apply_border_ring(result.layers["kind"], 2)

def ensure_connectivity(kind: List[List[str]], height_grid: List[List[float]], points: List[Tuple[int, int]], paths: List) -> None:
    """
    Гарантирует связность для 2-х портов, если "честный" путь не нашелся,
    создавая аварийный прямой путь.
    """
    if len(points) == 2 and paths and paths[0] is None:
        start, end = points[0], points[1]
        emergency_path = []
        x1, z1 = start
        x2, z2 = end
        steps = max(abs(x2 - x1), abs(z2 - z1))
        # Защита от деления на ноль, если точки совпадают
        if steps == 0: return
        for i in range(steps + 1):
            t = i / steps
            x, z = round(x1 + t * (x2 - x1)), round(z1 + t * (z2 - z1))
            emergency_path.append((x, z))
        # Используем уже существующую функцию для прокладки пути
        carve_path_emergency(kind, emergency_path)