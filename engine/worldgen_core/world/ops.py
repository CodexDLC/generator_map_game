from __future__ import annotations
from typing import Any, Dict, List, Tuple
from ..base.generator import KIND_GROUND, KIND_OBSTACLE, KIND_WATER
from ..base.rng import RNG, edge_key
from ..grid_alg.features import fbm2d  # шум для hint/halo
from ..utils.rle import encode_rle_line, encode_rle_rows


# ---------- Кромка/порты ----------

def side_neighbor(cx: int, cz: int, side: str) -> Tuple[int, int]:
    if side == "N": return cx, cz - 1
    if side == "S": return cx, cz + 1
    if side == "W": return cx - 1, cz
    if side == "E": return cx + 1, cz
    raise ValueError(side)

def apply_border_ring(kind: List[List[str]], t: int) -> None:
    """Делаем непроходимую рамку толщиной t (окна портов прорежем отдельно)."""
    h = len(kind); w = len(kind[0]) if h else 0
    t = max(0, min(t, min(w, h)//2))
    if t == 0: return
    for z in range(h):
        for x in range(w):
            if z < t or z >= h - t or x < t or x >= w - t:
                kind[z][x] = KIND_OBSTACLE

def carve_port_window(kind: List[List[str]], side: str, idx: int, t: int, width: int) -> None:
    """Прорезаем окно шириной >=3 в рамке на стороне side, позиция idx вдоль стороны."""
    h = len(kind); w = len(kind[0]) if h else 0
    r = max(1, width // 2)
    if side == "N":
        for z in range(0, t):
            for x in range(max(0, idx - r), min(w, idx + r + 1)):
                kind[z][x] = KIND_GROUND
    elif side == "S":
        for z in range(h - t, h):
            for x in range(max(0, idx - r), min(w, idx + r + 1)):
                kind[z][x] = KIND_GROUND
    elif side == "W":
        for x in range(0, t):
            for z in range(max(0, idx - r), min(h, idx + r + 1)):
                kind[z][x] = KIND_GROUND
    elif side == "E":
        for x in range(w - t, w):
            for z in range(max(0, idx - r), min(h, idx + r + 1)):
                kind[z][x] = KIND_GROUND

def inner_point_for_side(side: str, idx: int, size: int, t: int) -> Tuple[int, int]:
    """Точка внутри чанка сразу за рамкой — старт коридора."""
    if side == "N": return idx, t
    if side == "S": return idx, size - 1 - t
    if side == "W": return t, idx
    if side == "E": return size - 1 - t, idx
    raise ValueError(side)


def choose_ports(seed: int, cx: int, cz: int, size: int, cfg: Dict[str, Any], params: Dict[str, Any], kind_grid: List[List[str]]) -> Dict[str, List[int]]:
    """
    Определяет активные порты, стараясь размещать их на проходимой земле.
    """
    margin = int(cfg.get("edge_margin", 3))
    sides = ["N", "E", "S", "W"]
    opposite = {"N": "S", "S": "N", "W": "E", "E": "W"}

    # --- Функция для поиска лучшей точки на границе ---
    def find_best_pos(r: RNG, side: str) -> int:
        positions = list(range(margin, size - margin))
        r.shuffle(positions)  # Создаем детерминированный список кандидатов

        # Ищем первую попавшуюся клетку с землей
        for pos in positions:
            if side == "N" and kind_grid[0][pos] == KIND_GROUND: return pos
            if side == "S" and kind_grid[size - 1][pos] == KIND_GROUND: return pos
            if side == "W" and kind_grid[pos][0] == KIND_GROUND: return pos
            if side == "E" and kind_grid[pos][size - 1] == KIND_GROUND: return pos

        # Если вся граница непроходима, возвращаем первого кандидата как запасной вариант
        return positions[0]

    # --- Шаг 0: Рассчитываем веса и позиции для всех сторон ---
    this_h: Dict[str, int] = {}
    this_pos: Dict[str, int] = {}
    for side in sides:
        nx, nz = side_neighbor(cx, cz, side)
        k = edge_key(seed, cx, cz, nx, nz)
        r = RNG(k)
        this_h[side] = r.u32()
        # Позиция теперь ищется с помощью новой умной функции
        this_pos[side] = find_best_pos(r, side)

    # --- Шаг 1: Применяем "желания" (уклон для веток) ---
    world_id = str(params.get("world_id", "city"))
    result: Dict[str, List[int]] = {s: [] for s in sides}
    active_ports = set()

    if world_id.startswith("branch/"):
        branch_side = world_id.split('/', 1)[1]
        bias = float(params.get("branch_bias", 0.3))  # Шанс на доп. ветвление

        for side in sides:
            r = RNG(edge_key(seed, cx, cz, *side_neighbor(cx, cz, side)))
            is_active = False
            # Вероятность открытия зависит от направления
            if side == branch_side:  # Вперед
                is_active = r.uniform() < (0.6 + bias)  # Очень высокий шанс
            elif side != opposite[branch_side]:  # Вбок
                is_active = r.uniform() < (0.1 + bias / 2)  # Низкий шанс
            else:  # Назад, к городу
                is_active = r.uniform() < 0.5  # Средний шанс

            if is_active:
                result[side] = [this_pos[side]]
                active_ports.add(side)

    # --- Шаг 2: Обеспечиваем "необходимость" (гарантия связности) ---
    # Если мы не в ветке или портов получилось мало, применяем базовое правило
    min_ports = 1 if world_id.startswith("branch/") else 2  # В ветках допустимы тупики

    if len(active_ports) < min_ports:
        # Сортируем стороны по весу, чтобы гарантировать одинаковый результат у соседей
        sorted_sides = sorted(sides, key=lambda s: this_h[s])

        # Принудительно открываем порты, пока не достигнем минимума
        for side in sorted_sides:
            if len(active_ports) >= min_ports:
                break
            if not result[side]:  # Если порт еще не открыт
                result[side] = [this_pos[side]]
                active_ports.add(side)

    return result

# ---------- Пути/коридоры ----------

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


# ---------- Hint/Halo и кромки ----------

def kind_to_id(v: str) -> int:
    return 0 if v == KIND_GROUND else (1 if v == KIND_OBSTACLE else 2)

def kind_to_pass(v: str) -> int:
    return 1 if v == KIND_GROUND else 0

def edges_tiles_and_pass_from_kind(kind: List[List[str]]) -> Dict[str, Any]:
    h = len(kind); w = len(kind[0]) if h else 0
    north = [kind[0][x]     for x in range(w)]
    south = [kind[h-1][x]   for x in range(w)]
    west  = [kind[z][0]     for z in range(h)]
    east  = [kind[z][w-1]   for z in range(h)]
    return {
        "N": {"tiles": encode_rle_line([kind_to_id(v) for v in north]),
              "pass":  encode_rle_line([kind_to_pass(v) for v in north])},
        "S": {"tiles": encode_rle_line([kind_to_id(v) for v in south]),
              "pass":  encode_rle_line([kind_to_pass(v) for v in south])},
        "W": {"tiles": encode_rle_line([kind_to_id(v) for v in west]),
              "pass":  encode_rle_line([kind_to_pass(v) for v in west])},
        "E": {"tiles": encode_rle_line([kind_to_id(v) for v in east]),
              "pass":  encode_rle_line([kind_to_pass(v) for v in east])},
    }

def compute_hint_and_halo(
    stage_seeds: Dict[str,int], cx: int, cz: int, size: int,
    obs_cfg: Dict[str, Any], wat_cfg: Dict[str, Any], halo_t: int
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """hint — одна линия сразу за границей; halo — t полос за границей."""
    od = float(obs_cfg.get("density", 0.12))
    ofreq = float(obs_cfg.get("freq", 1.0/28.0))
    ooct = int(obs_cfg.get("octaves", 3))
    wd = float(wat_cfg.get("density", 0.05))
    wfreq = float(wat_cfg.get("freq", 1.0/20.0))
    woct = int(wat_cfg.get("octaves", 3))

    def sample_kind(wx: int, wz: int) -> int:
        n_obs = fbm2d(stage_seeds["obstacles"], float(wx), float(wz), ofreq, octaves=ooct)
        n_w   = fbm2d(stage_seeds["water"],     float(wx), float(wz), wfreq,  octaves=woct)
        if n_w < wd: return 2
        return 1 if n_obs < od else 0

    top_wz    = cz*size - 1
    bottom_wz = cz*size + size
    left_wx   = cx*size - 1
    right_wx  = cx*size + size

    hint = {"N": {}, "S": {}, "W": {}, "E": {}}
    halo = {"N": {}, "S": {}, "W": {}, "E": {}}

    # N/S — по X, W/E — по Z
    n_line = [sample_kind(cx*size + x, top_wz) for x in range(size)]
    hint["N"] = encode_rle_rows([n_line])
    n_rows = [[sample_kind(cx*size + x, top_wz - r) for x in range(size)] for r in range(halo_t, 0, -1)]
    halo["N"] = encode_rle_rows(n_rows)

    s_line = [sample_kind(cx*size + x, bottom_wz) for x in range(size)]
    hint["S"] = encode_rle_rows([s_line])
    s_rows = [[sample_kind(cx*size + x, bottom_wz + r - 1) for x in range(size)] for r in range(1, halo_t+1)]
    halo["S"] = encode_rle_rows(s_rows)

    w_line = [sample_kind(left_wx, cz*size + z) for z in range(size)]
    hint["W"] = encode_rle_rows([[v] for v in w_line])
    w_rows = [[sample_kind(left_wx - r, cz*size + z) for z in range(size)] for r in range(halo_t, 0, -1)]
    halo["W"] = encode_rle_rows(w_rows)

    e_line = [sample_kind(right_wx, cz*size + z) for z in range(size)]
    hint["E"] = encode_rle_rows([[v] for v in e_line])
    e_rows = [[sample_kind(right_wx + r - 1, cz*size + z) for z in range(size)] for r in range(1, halo_t+1)]
    halo["E"] = encode_rle_rows(e_rows)

    return hint, halo
