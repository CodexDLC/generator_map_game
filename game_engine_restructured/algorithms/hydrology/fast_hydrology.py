# Файл: game_engine_restructured/algorithms/hydrology/fast_hydrology.py
from __future__ import annotations

from typing import Tuple

import numpy as np
from numba import njit, prange

# Кодирование направлений D8: 0=E, 1=NE, 2=N, 3=NW, 4=W, 5=SW, 6=S, 7=SE
D8_NEIGHBORS = np.array([
    [0, 1], [-1, 1], [-1, 0], [-1, -1],
    [0, -1], [1, -1], [1, 0], [1, 1]
], dtype=np.int8)


@njit(cache=True, fastmath=True)
def _build_d8_flow_directions(heights: np.ndarray) -> np.ndarray:
    """
    Для каждой клетки находит направление наискорейшего спуска (D8).
    Возвращает индекс направления (0-7) или -1, если клетка - локальный минимум.
    """
    h, w = heights.shape
    dirs = np.full((h, w), -1, dtype=np.int8)
    for z in prange(h):
        for x in range(w):
            min_h = heights[z, x]
            best_dir = -1
            # Находим самого низкого соседа
            for i in range(8):
                dz, dx = D8_NEIGHBORS[i]
                nz, nx = z + dz, x + dx
                if 0 <= nz < h and 0 <= nx < w:
                    neighbor_h = heights[nz, nx]
                    # noinspection PyTypeChecker
                    if neighbor_h < min_h:
                        min_h = neighbor_h
                        best_dir = i
            dirs[z, x] = best_dir
    return dirs


@njit(cache=True, fastmath=True)
def _flow_accumulation_from_dirs(
        heights: np.ndarray, flow_dirs: np.ndarray
) -> np.ndarray:
    """
    Вычисляет накопление потока (flow accumulation), используя заранее
    рассчитанную карту направлений.
    """
    h, w = heights.shape
    flow_map = np.ones((h, w), dtype=np.float32)

    # Получаем плоский отсортированный список индексов от самого высокого к самому низкому
    # Это гарантирует, что мы обрабатываем клетки в правильном порядке (сверху вниз)
    sorted_indices = np.argsort(heights.ravel())[::-1]

    for idx in sorted_indices:
        z, x = idx // w, idx % w
        direction = flow_dirs[z, x]
        if direction != -1:  # Если это не локальный минимум
            dz, dx = D8_NEIGHBORS[direction]
            nz, nx = z + dz, x + dx
            if 0 <= nz < h and 0 <= nx < w:
                flow_map[nz, nx] += flow_map[z, x]
    return flow_map


@njit(cache=True, fastmath=True, parallel=True)
def _chamfer_distance_transform(mask: np.ndarray) -> np.ndarray:
    """
    Быстрый двухпроходный алгоритм Distance Transform (Chamfer).
    Гораздо быстрее, чем евклидовский вариант из scipy.
    """
    h, w = mask.shape
    dist = np.full((h, w), 1e9, dtype=np.float32)

    # Инициализация: 0 где маска, иначе "бесконечность"
    for z in prange(h):
        for x in range(w):
            if mask[z, x]:
                dist[z, x] = 0.0

    # Проход 1: Сверху-вниз, слева-направо
    for z in range(1, h):
        for x in range(1, w):
            # noinspection PyTypeChecker
            dist[z, x] = min(dist[z, x], dist[z - 1, x] + 1.0, dist[z, x - 1] + 1.0)

    # Проход 2: Снизу-вверх, справа-налево
    for z in range(h - 2, -1, -1):
        for x in range(w - 2, -1, -1):
            # noinspection PyTypeChecker
            dist[z, x] = min(dist[z, x], dist[z + 1, x] + 1.0, dist[z, x + 1] + 1.0)

    return dist


@njit(cache=True)
def _label_connected_components(mask: np.ndarray) -> Tuple[np.ndarray, int]:
    """
    Простой Numba-совместимый аналог scipy.ndimage.label для подсчета
    связных компонентов (истоков рек).
    """
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    label_count = 0

    for z in range(h):
        for x in range(w):
            if mask[z, x] and labels[z, x] == 0:
                label_count += 1
                q = [(z, x)]
                labels[z, x] = label_count
                head = 0
                while head < len(q):
                    cz, cx = q[head]
                    head += 1
                    for dz in range(-1, 2):
                        for dx in range(-1, 2):
                            if dz == 0 and dx == 0: continue
                            nz, nx = cz + dz, cx + dx
                            if 0 <= nz < h and 0 <= nx < w and mask[nz, nx] and labels[nz, nx] == 0:
                                labels[nz, nx] = label_count
                                q.append((nz, nx))
    return labels, label_count