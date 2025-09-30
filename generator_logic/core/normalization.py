# ======================================================================
# Файл: game_engine_restructured/numerics/normalization.py
# Назначение: Универсальная нормализация шумов/высот в [0..1] + округление.
# ======================================================================
from __future__ import annotations
import numpy as np
from numba import njit, prange

EPS = 1e-12

@njit(cache=True, fastmath=True, parallel=True)
def _replace_nan_inplace(a: np.ndarray, value: float) -> None:
    H, W = a.shape
    for j in prange(H):
        for i in range(W):
            v = a[j, i]
            if not np.isfinite(v):
                a[j, i] = value

@njit(cache=True, fastmath=True, parallel=True)
def _clamp01_inplace(a: np.ndarray) -> None:
    H, W = a.shape
    for j in prange(H):
        for i in range(W):
            v = a[j, i]
            if v < 0.0:
                a[j, i] = 0.0
            elif v > 1.0:
                a[j, i] = 1.0

@njit(cache=True, fastmath=True, parallel=True)
def _minmax_inplace(a: np.ndarray, lo: float, hi: float) -> None:
    den = hi - lo
    if den < EPS:
        # массив почти константный — оставим как есть, дальше обработаем снаружи
        return
    inv = 1.0 / den
    H, W = a.shape
    for j in prange(H):
        for i in range(W):
            a[j, i] = (a[j, i] - lo) * inv

@njit(cache=True, fastmath=True, parallel=True)
def _symmetric_inplace(a: np.ndarray, A: float) -> None:
    # map [-A..A] -> [0..1] линейно через 0.5
    if A < EPS:
        return
    invA = 1.0 / (2.0 * A)
    H, W = a.shape
    for j in prange(H):
        for i in range(W):
            a[j, i] = 0.5 + 0.5 * (a[j, i] * (1.0 / A))  # 0.5*(x/A)+0.5

@njit(cache=True, fastmath=True, parallel=True)
def _round_decimals_inplace(a: np.ndarray, decimals: int) -> None:
    if decimals <= 0:
        return
    scale = 1.0
    for _ in range(decimals):
        scale *= 10.0
    inv = 1.0 / scale
    H, W = a.shape
    for j in prange(H):
        for i in range(W):
            # Быстрая “банковская” близкая к round: floor(x*scale+0.5)/scale
            x = a[j, i] * scale
            if x >= 0.0:
                y = np.floor(x + 0.5)
            else:
                y = -np.floor(-x + 0.5)
            a[j, i] = y * inv

def _choose_auto_mode(hmin: float, hmax: float) -> str:
    # “Двуполярный” если есть знак и отрицательная часть сопоставима по модулю
    if hmin < 0.0 and hmax > 0.0:
        ratio = abs(hmin) / (hmax + EPS)
        if 0.5 <= ratio <= 2.0:
            return "symmetric"
    return "minmax"

def normalize01(
    arr: np.ndarray,
    mode: str = "auto",              # "auto" | "minmax" | "symmetric" | "clamp01"
    min_override: float | None = None,
    max_override: float | None = None,
    clip_after: bool = True,
    decimals: int = 0,               # 0 = без округления
    nan_fill: float = 0.0,
    fill_const: float = 0.0          # на случай константного входа
) -> np.ndarray:
    """
    Превращает произвольную карту в [0..1] по выбранной стратегии, устойчиво к NaN.
    Возвращает float32 массив.
    """
    if arr is None:
        return np.zeros((1, 1), dtype=np.float32)
    a = np.array(arr, dtype=np.float32, copy=True)

    # 1) NaN -> nan_fill
    _replace_nan_inplace(a, float(nan_fill))

    # 2) Статистики
    hmin = float(np.nanmin(a))
    hmax = float(np.nanmax(a))

    # Константный массив
    if not np.isfinite(hmin) or not np.isfinite(hmax) or abs(hmax - hmin) < EPS:
        a[:] = float(fill_const)
        if decimals > 0:
            _round_decimals_inplace(a, int(decimals))
        if clip_after:
            _clamp01_inplace(a)
        return a

    # 3) Выбор и применение нормализации
    m = mode.lower()
    if m == "clamp01":
        _clamp01_inplace(a)

    elif m == "symmetric" or (m == "auto" and _choose_auto_mode(hmin, hmax) == "symmetric"):
        A = max(abs(hmin), abs(hmax))
        _symmetric_inplace(a, A)

    else:  # "minmax" или auto->minmax
        lo = float(min_override) if min_override is not None else hmin
        hi = float(max_override) if max_override is not None else hmax
        _minmax_inplace(a, lo, hi)

    # 4) Опциональные шаги
    if clip_after:
        _clamp01_inplace(a)
    if decimals > 0:
        _round_decimals_inplace(a, int(decimals))
        if clip_after:
            _clamp01_inplace(a)

    return a
