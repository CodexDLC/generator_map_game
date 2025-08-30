from typing import List, Tuple

from engine.worldgen_core.base.constants import KIND_GROUND, KIND_OBSTACLE, KIND_WATER, KIND_ROAD
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

def apply_paths_to_grid(kind_grid: List[List[str]], paths: List[List[Tuple[int, int]] | None]):
    """
    "Рисует" найденные пути на карте, заменяя тайлы на KIND_ROAD.
    """
    if not paths: return
    for path in paths:
        if path:
            for x, z in path:
                # Рисуем дорогу, только если там сейчас земля (не трогаем воду и скалы)
                if kind_grid[z][x] == KIND_GROUND:
                    kind_grid[z][x] = KIND_ROAD

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
    Находит сеть путей, соединяющих все точки, используя Minimum Spanning Tree (MST).
    Это создает более естественные Y-образные перекрестки.
    """
    if len(points) < 2:
        return []

    # Шаг 1: Рассчитать стоимость пути между каждой парой точек
    # Это "ребра" нашего полного графа
    edges = []
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            path = dijkstra_path(kind, height_grid, points[i], points[j])
            if path:
                # Стоимость = длина пути
                cost = len(path)
                # Сохраняем стоимость, начальную и конечную точки, и сам путь
                edges.append((cost, points[i], points[j], path))

    # Сортируем ребра от самых дешевых к самым дорогим
    edges.sort(key=lambda x: x[0])

    # Шаг 2: Алгоритм Прима/Крускала для построения MST
    parent = {point: point for point in points}

    def find_set(p):
        if p == parent[p]:
            return p
        parent[p] = find_set(parent[p])
        return parent[p]

    def unite_sets(a, b):
        a = find_set(a)
        b = find_set(b)
        if a != b:
            parent[b] = a
            return True
        return False

    final_paths = []
    for cost, p1, p2, path_data in edges:
        # Если точки еще не соединены, добавляем этот путь
        if unite_sets(p1, p2):
            final_paths.append(path_data)

    return final_paths

def add_border(self, result: GenResult):
    apply_border_ring(result.layers["kind"], 2)


def ensure_connectivity(kind: List[List[str]], height_grid: List[List[float]], points: List[Tuple[int, int]],
                        paths: List) -> None:
    """
    Гарантирует связность, создавая аварийный путь, если "честный" не нашелся.
    """
    if len(points) < 2 or not paths:
        return

    # Проверяем, все ли точки соединены с первой точкой
    # (Для MST этого может быть недостаточно, но для начала сойдет)
    if any(p is None for p in paths):
        # Находим все точки, до которых не удалось построить путь
        connected_points = {points[0]}
        for i, path in enumerate(paths):
            if path:
                # В MST пути могут быть между разными точками
                connected_points.add(path[0])
                connected_points.add(path[-1])

        unconnected_points = [p for p in points if p not in connected_points]

        # Для каждой отсоединенной точки строим аварийный путь к ближайшей соединенной
        for point_a in unconnected_points:
            # Находим ближайшую соединенную точку (упрощенно)
            point_b = min(connected_points, key=lambda p: (p[0] - point_a[0]) ** 2 + (p[1] - point_a[1]) ** 2)

            emergency_path = []
            x1, z1 = point_a
            x2, z2 = point_b
            steps = max(abs(x2 - x1), abs(z2 - z1))
            if steps == 0: continue
            for step in range(steps + 1):
                t = step / steps
                x = round(x1 + t * (x2 - x1))
                z = round(z1 + t * (z2 - z1))
                emergency_path.append((x, z))

            # Пробиваем туннель
            for x, z in emergency_path:
                if 0 <= z < len(kind) and 0 <= x < len(kind[0]):
                    kind[z][x] = KIND_GROUND

            # Добавляем этот путь, чтобы по нему тоже нарисовали дорогу
            paths.append(emergency_path)