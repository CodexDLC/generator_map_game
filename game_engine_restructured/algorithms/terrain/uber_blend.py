"""
uber_blend.py — утилиты для бесшовного склеивания регионов/стилей и морфинга шума.

Функции:
- donut_mask(world_x, world_z, region_bounds, blend_width_m, inner_pad_m=0)
    Строит пончиковую маску M(x)∈[0,1]:
      M=1 в ядре региона, плавно падает к 0 на внешнем кольце шириной blend_width_m.
    Используется для бесшовного склеивания: H = lerp(H_base, H_style, M).

- blend_seamless(H_base, H_style, M)
    Бленд без швов: вернёт H = (1-M)*H_base + M*H_style.

- align_style_gain(H_style, H_base, clamp=(0.85, 1.15))
    Подгоняет контраст стиля к базе на области перехода: подбирает gain, чтобы
    дисперсия и среднее совпали (стабильный R16/H_NORM вид). Возвращает H_style_aligned, gain, offset.

- seam_rmse_along_border(H, region_bounds, border="all", band_m=2*cell_size)
    Диагностическая оценка шва: RMSE вдоль полосы по периметру. Можно сравнить с соседями.

- morph_wave_ridge(n, k, sharpness_enhance=0.0)
    Морф одной октавы базового шума n∈[-1,1] в billow/base/ridge по карте k∈[-1,1].

- uber_fbm(...)
    Реализация fBm с морфингом формы и простыми «эрозиями» (по уклону/высоте/гребням).
    Нужен коллбэк noise2d(u, v, seed) → [-1,1]. Для slope-erosion используются центральные разности.

Интеграция (коротко):
1) Сгенерируй глобальную базу G(x) обычным способом.
2) Сгенерируй стиль H_style(x) (те же координаты, твои слои/маски/параметры).
3) Построй M = donut_mask(...). Затем H = blend_seamless(G, align_style_gain(H_style, G)[0], M).
4) Дальше твои террасы/вода/лимитер → экспорт.
"""
from __future__ import annotations
import numpy as np
from typing import Tuple, Literal, Callable

# -------------------------
# ВСПОМОГАТЕЛЬНЫЕ ПРОЦЕДУРЫ
# -------------------------

def smoothstep(edge0: float, edge1: float, x: np.ndarray) -> np.ndarray:
    """GLSL-like smoothstep с защитой от edge0==edge1."""
    e0, e1 = float(edge0), float(edge1)
    if e0 == e1:
        return (x >= e1).astype(np.float32)
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return (t * t * (3.0 - 2.0 * t)).astype(np.float32)


def lerp(a: np.ndarray, b: np.ndarray, w: np.ndarray) -> np.ndarray:
    return (a * (1.0 - w) + b * w).astype(np.float32)


# -----------------------------------------
# ПОНЧИКОВАЯ МАСКА ДЛЯ БЕСШОВНОГО СКЛЕИВАНИЯ
# -----------------------------------------

def donut_mask(
    world_x: np.ndarray,
    world_z: np.ndarray,
    region_bounds: Tuple[float, float, float, float],
    blend_width_m: float,
    inner_pad_m: float = 0.0,
    falloff: Literal["smoothstep", "linear", "cosine"] = "smoothstep",
) -> np.ndarray:
    """Строит маску M∈[0,1]: 1 в ядре региона, 0 на внешнем кольце шириной blend_width_m.

    - world_x, world_z: мировые координаты каждого пикселя (массивы одной формы).
    - region_bounds: (xmin, xmax, zmin, zmax) региона (в метрах, глобальная система).
    - inner_pad_m: необязательный внутренний отступ от края ядра (оставляет «полезную область»).
    - falloff: тип спадания к краю.

    Формула: M = f( dist_to_border / blend_width_m ), где f — одна из кривых.
    На самой границе региона M≈0, на расстоянии >= blend_width_m — M≈1.
    """
    xmin, xmax, zmin, zmax = map(float, region_bounds)
    # расстояние до ближайшей стороны прямоугольника
    dx = np.minimum(world_x - xmin, xmax - world_x)
    dz = np.minimum(world_z - zmin, zmax - world_z)
    dist = np.minimum(dx, dz)  # метрическая «сколь близко к краю»

    # внутренняя «полезная» зона до начала спада
    dist = np.maximum(0.0, dist - float(inner_pad_m))
    w = np.clip(dist / max(1e-6, float(blend_width_m)), 0.0, 1.0)

    if falloff == "linear":
        M = w
    elif falloff == "cosine":
        # плавная полка: 0..1 → 0..1 через полуволну косинуса
        M = (1 - np.cos(np.pi * w)) * 0.5
    else:  # smoothstep
        M = smoothstep(0.0, 1.0, w)

    return M.astype(np.float32)


def blend_seamless(H_base: np.ndarray, H_style: np.ndarray, M: np.ndarray) -> np.ndarray:
    """Бесшовный бленд: H = (1-M)*H_base + M*H_style. Все массивы одной формы."""
    H_base = np.nan_to_num(H_base, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
    H_style = np.nan_to_num(H_style, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
    M = np.clip(M, 0.0, 1.0).astype(np.float32)
    return lerp(H_base, H_style, M)


def align_style_gain(
    H_style: np.ndarray,
    H_base: np.ndarray,
    mask: np.ndarray | None = None,
    clamp: Tuple[float, float] = (0.85, 1.15),
) -> Tuple[np.ndarray, float, float]:
    """Подгоняет стиль к базе по среднему и дисперсии на указанной маске (обычно зона перехода).
    Возвращает (H_style_aligned, gain, offset).
    """
    if mask is None:
        # По умолчанию работаем на всей области
        mask = np.ones_like(H_base, dtype=np.float32)
    mask = mask.astype(bool)

    bs = H_base[mask].astype(np.float64)
    ss = H_style[mask].astype(np.float64)
    if bs.size < 8:
        return H_style.astype(np.float32), 1.0, 0.0
    
    mb, sb = bs.mean(), bs.std() + 1e-6
    ms, ssig = ss.mean(), ss.std() + 1e-6

    gain = float(np.clip(sb / ssig, clamp[0], clamp[1]))
    offset = float(mb - gain * ms)

    H_adj = (H_style.astype(np.float32) * gain + offset).astype(np.float32)
    return H_adj, gain, offset


def seam_rmse_along_border(
    H: np.ndarray,
    region_bounds: Tuple[float, float, float, float],
    cell_size_m: float,
    band_m: float,
) -> float:
    """Упрощённая метрика: RMSE вариации высоты вдоль полосы у края региона.
    Полезно как «алерт», если после бленда остаются резкие изменения.
    """
    h, w = H.shape
    band = max(1, int(round(band_m / max(1e-6, cell_size_m))))
    edge_vals = np.concatenate([
        H[:band, :].ravel(),
        H[-band:, :].ravel(),
        H[:, :band].ravel(),
        H[:, -band:].ravel(),
    ])
    # RMSE относительно среднего в полосе (чем меньше, тем гладче)
    mu = float(edge_vals.mean())
    rmse = float(np.sqrt(np.mean((edge_vals - mu) ** 2)))
    return rmse


# ------------------------------------
# МОРФ ФОРМЫ ШУМА И «ДЕШЁВЫЕ ЭРОЗИИ»
# ------------------------------------

def morph_wave_ridge(n: np.ndarray, k: np.ndarray, sharpness_enhance: float = 0.0) -> np.ndarray:
    """Морф одной октавы n∈[-1,1] между billow/base/ridge по карте k∈[-1,1].
    k>0 → ridge, k<0 → billow, k≈0 → base. sharpness_enhance ≥ 0 усиливает «остроту»."""
    n = np.clip(n, -1.0, 1.0).astype(np.float32)
    k = np.clip(k, -1.0, 1.0).astype(np.float32)
    t_r = np.maximum(0.0, k)
    t_b = np.maximum(0.0, -k)
    b = 2.0 * np.abs(n) - 1.0
    r = 1.0 - 2.0 * np.abs(n)
    out = n * (1.0 - t_r - t_b) + r * t_r + b * t_b
    if sharpness_enhance > 0.0:
        s = 1.0 + float(sharpness_enhance)
        out = np.sign(out) * (np.abs(out) ** s)
    return np.clip(out, -1.0, 1.0).astype(np.float32)


def uber_fbm(
    world_x: np.ndarray,
    world_z: np.ndarray,
    *,
    base_period_m: float,
    octaves: int = 5,
    lacunarity: float = 2.0,
    gain: float = 0.5,
    seed: int = 0,
    # карты-модуляторы (низкочастотные): функции noise2d(u,v,seed)->[-1,1]
    noise2d: Callable[[np.ndarray, np.ndarray, int, float], np.ndarray] | None = None,
    k_map_period_m: float | None = None,
    k_map_amp: float = 1.0,
    sharpness_enhance: float = 0.5,
    altitude_erosion: float = 0.5,
    ridge_erosion: float = 0.2,
    slope_erosion: float = 0.4,
) -> np.ndarray:
    """fBm с морфингом формы и простыми эрозиями.

    Параметр noise2d должен уметь: noise2d(U, V, seed, freq) → массив [-1,1] той же формы.
    Частота freq = 1/period_m (в 1/м). Если не передать noise2d — кинем исключение.
    """
    if noise2d is None:
        raise ValueError("uber_fbm: требуется noise2d(U,V,seed,freq) -> [-1,1]")

    U = world_x.astype(np.float32)
    V = world_z.astype(np.float32)

    # Карта формы k(x) ∈ [-1,1]
    if k_map_period_m is None:
        k_map_period_m = base_period_m * 1.25
    kfreq = 1.0 / max(1e-6, float(k_map_period_m))
    k = k_map_amp * noise2d(U, V, seed + 777, kfreq)
    k = np.clip(k, -1.0, 1.0).astype(np.float32)

    # Аккумулятор
    h = np.zeros_like(U, dtype=np.float32)
    amp = 1.0
    freq = 1.0 / max(1e-6, float(base_period_m))

    # Предварительные шаги для производных
    def derivs(nfunc, U, V, seed, freq, dx_m: float) -> Tuple[np.ndarray, np.ndarray]:
        # центральная разность по U/V
        n_pu = nfunc(U + dx_m, V, seed, freq)
        n_mu = nfunc(U - dx_m, V, seed, freq)
        n_pv = nfunc(U, V + dx_m, seed, freq)
        n_mv = nfunc(U, V - dx_m, seed, freq)
        du = (n_pu - n_mu) / (2.0 * dx_m)
        dv = (n_pv - n_mv) / (2.0 * dx_m)
        return du.astype(np.float32), dv.astype(np.float32)

    for o in range(int(octaves)):
        n = noise2d(U, V, seed + o * 13, freq)
        n = morph_wave_ridge(n, k, sharpness_enhance=sharpness_enhance)

        # ridge-маска для «эрозии гребней» (больше у гребней)
        ridge_mask = (1.0 - np.abs(n))
        ridge_mask = np.clip(ridge_mask, 0.0, 1.0)

        # Производные для «уклон-эрозии» (шаг = половина длины волны текущей октавы)
        dx = 0.5 / max(1e-6, freq)
        du, dv = derivs(noise2d, U, V, seed + o * 13, freq, dx)
        slope = np.sqrt(du * du + dv * dv)  # безразмерно

        # Демпферы амплитуды *перед* добавлением октавы
        amp_o = amp
        if altitude_erosion > 0.0:
            # Нормируем текущую накопленную высоту к [0,1] через сигмоиду
            h_norm = 0.5 + 0.5 * np.tanh(h)
            amp_o *= (1.0 - altitude_erosion) + altitude_erosion * (1.0 - h_norm)
        if ridge_erosion > 0.0:
            amp_o *= (1.0 - ridge_erosion * ridge_mask)
        if slope_erosion > 0.0:
            amp_o *= 1.0 / (1.0 + (slope_erosion * slope) ** 2)

        h += (n * amp_o).astype(np.float32)

        # переход к следующей октаве
        freq *= float(lacunarity)
        amp *= float(gain)

    # Нормализация под классический fbm_amplitude
    # сумма геометрической прогрессии с gain, начиная с 1.0
    if gain != 1.0:
        norm = (1.0 - gain ** octaves) / (1.0 - gain)
    else:
        norm = float(octaves)
    h /= max(1e-6, norm)
    return np.clip(h, -1.0, 1.0).astype(np.float32)

# ---------------------------------
# НОВАЯ ФУНКЦИЯ: ГЕКСАГОНАЛЬНАЯ МАСКА
# ---------------------------------

def hex_mask(
    shape: Tuple[int, int],
    blend_width_pct: float = 0.20,
) -> np.ndarray:
    """
    Создает маску M∈[0,1] в виде гексагона, вписанного в квадратный массив.

    Имеет сплошной центр (значение 1.0) и плавно затухающие края.
    - shape: (height, width) квадратного массива.
    - blend_width_pct: Ширина зоны смешивания в процентах от радиуса гексагона (0.2 = 20%).
    """
    h, w = shape
    if h != w:
        raise ValueError("Функция hex_mask ожидает квадратную форму массива.")

    # Создаем сетку координат от -1 до 1 с центром в (0,0)
    x = np.linspace(-1.0, 1.0, w, dtype=np.float32)
    y = np.linspace(-1.0, 1.0, h, dtype=np.float32)
    xv, yv = np.meshgrid(x, y)

    # Математика для определения расстояния до центра в гексагональной метрике
    # "Сплющивает" круг в гексагон
    q2x = xv
    q2y = -0.5 * xv + (np.sqrt(3.0) / 2.0) * yv
    q3y = -0.5 * xv - (np.sqrt(3.0) / 2.0) * yv
    
    hex_dist = np.maximum(np.abs(q2x), np.maximum(np.abs(q2y), np.abs(q3y)))

    # Определяем границы для плавного перехода
    inner_radius = 1.0 - max(0.0, min(1.0, blend_width_pct))
    
    # Инвертированный smoothstep, чтобы в центре был 1, а по краям 0
    mask = 1.0 - smoothstep(inner_radius, 1.0, hex_dist)

    return mask.astype(np.float32)