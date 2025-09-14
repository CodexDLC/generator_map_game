# ==============================================================================
# Файл: game_engine_restructured/algorithms/terrain/terrain.py
# Назначение: Генерация геометрии ландшафта (карты высот).
# ВЕРСИЯ 12.1: Подушка (large_features) сделана положительной (positive_only),
#              амплитудная нормализация fBm, мягкий клип, анизотропия,
#              опциональный авто-подбор итераций лимитера уклона.
# ==============================================================================

from __future__ import annotations
from typing import Any, Dict
import math
import numpy as np
from scipy.ndimage import gaussian_filter

from .slope import _apply_slope_limiter
from ...core.noise.fast_noise import fbm_grid, fbm_amplitude, fbm_grid_warped


# ==============================================================================
# --- БЛОК 1: Вспомогательные утилиты ---
# ==============================================================================

def _apply_shaping_curve(grid: np.ndarray, power: float) -> None:
    """
    Возведение массива в степень (в месте), чтобы 'растянуть' верх/низ распределения.
    Для базовых слоёв (в [0..1]) даёт "сухие" пики при power>1.
    """
    if power != 1.0:
        np.power(grid, power, out=grid)


def _print_range(tag: str, arr: np.ndarray) -> None:
    """Диапазон значений для быстрой диагностики."""
    mn, mx = float(np.min(arr)), float(np.max(arr))
    print(f"[CHECK] {tag}: min={mn:.2f} max={mx:.2f} rng={mx - mn:.2f}")


def _vectorized_smoothstep(x: np.ndarray, edge0: float, edge1: float) -> np.ndarray:
    """
    Векторизованный smoothstep: 0 до edge0, 1 после edge1, плавный рост между.
    Используем для мягких порогов (включение гор, маски разрывов и т. п.).
    """
    if edge0 >= edge1:
        return np.where(x < edge0, 0.0, 1.0)
    t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ==============================================================================
# --- БЛОК 2: Универсальная функция генерации слоя ---
# ==============================================================================

def _generate_layer(
    seed: int,
    layer_cfg: Dict,
    base_coords_x: np.ndarray,
    base_coords_z: np.ndarray,
    cell_size: float,
    scratch_buffer: np.ndarray,
) -> np.ndarray:
    """
    Универсальный генератор слоя рельефа.
    Поддержка:
      - послойного domain warp;
      - анизотропии (разные масштабы вдоль/поперёк оси + поворот);
      - амплитудной нормализации fBm (стабильная шкала);
      - shaping (степень), мягких порогов (clip+softness);
      - модулатора разрывов 'breaks' вдоль гряды;
      - positive_only (сдвиг [-1..1] → [0..1]) для строго положительных вкладов.

    Ключевые флаги в layer_cfg:
      - is_base: True для базовых слоёв (континенты) — нормализуем в [0..1].
      - ridge: ridged fBm → гребни/хребты.
      - positive_only: принудительно сделать вклад неотрицательным ([0..1]).
    """
    amp = float(layer_cfg.get("amp_m", 0.0))
    if amp <= 0:
        return np.zeros_like(base_coords_x)

    # --- Шаг 1: Послойный Domain Warp (сдвиги координат шума) ---
    warp_cfg = layer_cfg.get("warp", {})
    warp_strength = float(warp_cfg.get("strength_m", 0.0))

    coords_x, coords_z = np.copy(base_coords_x), np.copy(base_coords_z)
    if warp_strength > 0:
        warp_scale = float(warp_cfg.get("scale_tiles", 1000)) * cell_size
        warp_freq = 1.0 / warp_scale if warp_scale > 0 else 0.0

        ext_size = base_coords_x.shape[0]
        # Стартовые индексы в "клетках" мира для бесшовности шума
        base_wx = int(math.floor(float(base_coords_x[0, 0]) / cell_size))
        base_wz = int(math.floor(float(base_coords_z[0, 0]) / cell_size))

        # Две независимые fBm для X и Z, нормируем на теоретическую амплитуду
        norm2 = fbm_amplitude(0.5, 2)
        warp_x_noise = fbm_grid(seed ^ 0x12345678, base_wx, base_wz, ext_size, cell_size, warp_freq, 2) / max(norm2, 1e-6)
        warp_z_noise = fbm_grid(seed ^ 0x87654321, base_wx, base_wz, ext_size, cell_size, warp_freq, 2) / max(norm2, 1e-6)

        coords_x += warp_x_noise * warp_strength
        coords_z += warp_z_noise * warp_strength

    # --- Шаг 2: Анизотропное масштабирование (поворот + разный масштаб) ---
    orientation = math.radians(float(layer_cfg.get("orientation_deg", 0.0)))
    aspect = float(layer_cfg.get("aspect", 1.0))

    scale_parallel = float(layer_cfg.get("scale_tiles_parallel", layer_cfg.get("scale_tiles", 1000))) * cell_size
    scale_perp = scale_parallel / aspect if aspect > 0 else scale_parallel

    if orientation != 0.0 or aspect != 1.0:
        cr, sr = math.cos(orientation), math.sin(orientation)
        final_coords_x_unscaled = (coords_x * cr - coords_z * sr)
        final_coords_z_unscaled = (coords_x * sr + coords_z * cr)
        final_coords_x = final_coords_x_unscaled / max(scale_parallel, 1e-9)
        final_coords_z = final_coords_z_unscaled / max(scale_perp, 1e-9)
        freq0 = 1.0  # частота уже "вшита" делением координат
    else:
        final_coords_x_unscaled = coords_x
        final_coords_z_unscaled = coords_z  # важно: держать определённым
        final_coords_x, final_coords_z = coords_x, coords_z
        freq0 = 1.0 / max(scale_parallel, 1e-9)

    # --- Шаг 3: Базовый шум (fBm или ridged fBm) ---
    octaves = int(layer_cfg.get("octaves", 3))
    is_ridge = bool(layer_cfg.get("ridge", False))
    noise = fbm_grid_warped(
        seed=seed,
        coords_x=final_coords_x,
        coords_z=final_coords_z,
        freq0=freq0,
        octaves=octaves,
        ridge=is_ridge,
    )

    # --- Шаг 4: Нормализация шкалы, shaping и локальные сглаживания ---
    is_base_layer = bool(layer_cfg.get("is_base", False))
    positive_only = bool(layer_cfg.get("positive_only", False))

    # Амплитудная нормализация: приводим к стабильной [-1..1] (или [0..1] для ridged base)
    norm_factor = max(fbm_amplitude(0.5, octaves), 1e-6)

    if is_base_layer:
        # БАЗА: приводим к [0..1], чтобы дальше "порог/шэйпинг" были инвариантны масштабу.
        if is_ridge:
            # ridged после деления уже ≥0; жёстко ограничим в [0..1]
            noise = noise / norm_factor
            np.clip(noise, 0.0, 1.0, out=noise)
        else:
            # обычный fBm → [-1..1] → [0..1]
            noise = noise / norm_factor
            np.clip(noise, -1.0, 1.0, out=noise)
            noise = 0.5 * (noise + 1.0)
    else:
        # АДДИТИВ: как правило хотим знаковый вклад ([-1..1]), иначе "замыливается".
        noise = noise / norm_factor
        np.clip(noise, -1.0, 1.0, out=noise)
        if positive_only:
            # Требуется строго положительный вклад → сдвиг в [0..1]
            noise = 0.5 * (noise + 1.0)

    # Пред-сглаживание перед степенью — снимает пилу ridged/FBM
    smoothing_sigma_pre_shape = float(layer_cfg.get("smoothing_sigma_pre_shape", 0.0))
    if smoothing_sigma_pre_shape > 0:
        gaussian_filter(noise, sigma=smoothing_sigma_pre_shape, output=scratch_buffer, mode="reflect")
        noise = np.copy(scratch_buffer)

    # Степенная аппроксимация (шэйпинг)
    shaping_power = float(layer_cfg.get("shaping_power", 1.0))
    if shaping_power != 1.0:
        if is_base_layer:
            # В [0..1] — обычная степень
            _apply_shaping_curve(noise, shaping_power)
        else:
            # Для знаковых шумов — степень по модулю, знак сохраняем
            signs = np.sign(noise)
            shaped = np.power(np.abs(noise), shaping_power)
            noise = shaped * signs

    # --- Шаг 5: Порог для базового слоя (включение гор без "стены") ---
    clip_threshold = float(layer_cfg.get("clip_threshold_post_shape", 0.0))
    clip_softness = float(layer_cfg.get("clip_softness", 0.0))  # ширина плавной рампы (в долях [0..1])

    if is_base_layer and clip_threshold > 0.0:
        if clip_softness <= 1e-6:
            # Жёсткий cut + линейная перенормализация верха в [0..1]
            t = clip_threshold
            np.clip(noise, t, 1.0, out=noise)
            if 1.0 - t > 1e-6:
                noise = (noise - t) / (1.0 - t)
        else:
            # Мягкий порог: ниже t0 → 0, между t0..t1 → плавный запуск, выше → линейно до 1
            t0 = max(0.0, clip_threshold - 0.5 * clip_softness)
            t1 = min(1.0, clip_threshold + 0.5 * clip_softness)
            m = _vectorized_smoothstep(noise, t0, t1)
            denom = max(1e-6, 1.0 - t0)
            z_lin = np.clip((noise - t0) / denom, 0.0, 1.0)
            noise = m * z_lin

    # --- Шаг 6: Модулятор разрывов хребта ("перевалы" по оси гряды) ---
    breaks_scale = float(layer_cfg.get("breaks_scale_tiles_parallel", 0.0))
    if breaks_scale > 0:
        breaks_freq = 1.0 / (breaks_scale * cell_size)
        # 1D-модулятор вдоль оси гряды: разрывы повторяются с характерным шагом
        mod = fbm_grid_warped(
            seed=seed ^ 0xCAFEBABE,
            coords_x=final_coords_x_unscaled * breaks_freq,
            coords_z=np.zeros_like(final_coords_x_unscaled),
            freq0=1.0,
            octaves=1,
        )
        mod = (mod / max(fbm_amplitude(0.5, 1), 1e-6) + 1.0) * 0.5  # → [0..1]
        frac = float(layer_cfg.get("breaks_fraction", 0.15))      # доля "убитых" сегментов
        soft = float(layer_cfg.get("breaks_softness", 0.05))      # мягкость маски
        edge0, edge1 = frac - soft * 0.5, frac + soft * 0.5
        mask = _vectorized_smoothstep(mod, edge0, edge1)
        noise *= mask  # задуваем часть хребта → перевалы/прокусы

    # --- Шаг 7: Пост-сглаживание и масштабирование по амплитуде ---
    smoothing_sigma_post_shape = float(layer_cfg.get("smoothing_sigma_post_shape", 0.0))
    if smoothing_sigma_post_shape > 0:
        gaussian_filter(noise, sigma=smoothing_sigma_post_shape, output=scratch_buffer, mode="reflect")
        noise = np.copy(scratch_buffer)

    return noise * amp


# ==============================================================================
# --- БЛОК 3: Главная функция-оркестратор (pipeline) ---
# ==============================================================================

def generate_elevation_region(
    seed: int,
    scx: int,
    scz: int,
    region_size_chunks: int,
    chunk_size: int,
    preset: Any,
    scratch_buffers: dict,
) -> np.ndarray:
    """
    Пайплайн генерации высоты региона:
      1) континенальный каркас (is_base=True) → [0..1] → shaping/clip/разрывы;
      2) подушка large_features (positive_only=True) — поднимает долины, не валит гряду;
      3) первый прогон лимитера уклона — склейка макро-слоёв без стен;
      4) средние/мелкие аддитивные детали (erosion/details);
      5) финальные пост-этапы (глобальное сглаживание*опционально*, сдвиг/клип).
    """
    # --- ЭТАП 0: Геометрия региона и служебные сетки ---
    cfg = getattr(preset, "elevation", {})
    spectral_cfg = cfg.get("spectral", {}) or {}

    ext_size = (region_size_chunks + 2) * chunk_size  # с 1-ячейковым бордером
    cell_size = float(getattr(preset, "cell_size", 1.0))
    base_wx = (scx * region_size_chunks - 1) * chunk_size
    base_wz = (scz * region_size_chunks - 1) * chunk_size

    # Глобальные координаты клеток (в метрах)
    z_coords_base, x_coords_base = np.mgrid[0:ext_size, 0:ext_size]
    x_coords_base = (x_coords_base.astype(np.float32) + base_wx) * cell_size
    z_coords_base = (z_coords_base.astype(np.float32) + base_wz) * cell_size

    height_grid = np.zeros((ext_size, ext_size), dtype=np.float32)

    # --- ЭТАП 1: Макрокаркас (Континенты + Подушка) ---
    # 1.1 Континенты
    if "continents" in spectral_cfg:
        layer_cfg = dict(spectral_cfg["continents"])
        layer_cfg["is_base"] = True  # базовый слой → в [0..1]
        print("  -> Generating layer: continents...")
        height_grid += _generate_layer(
            seed=seed,
            layer_cfg=layer_cfg,
            base_coords_x=x_coords_base,
            base_coords_z=z_coords_base,
            cell_size=cell_size,
            scratch_buffer=scratch_buffers["a"],
        )

    # 1.2 Подушка/равнины (large_features) — ДЕЛАЕМ ПОЛОЖИТЕЛЬНОЙ
    if "large_features" in spectral_cfg:
        layer_cfg = dict(spectral_cfg["large_features"])
        layer_cfg["is_base"] = False
        # ВАЖНО: подушка должна только поднимать рельеф (без отрицательных вкладов)
        layer_cfg.setdefault("positive_only", True)
        print("  -> Generating layer: large_features (cushion, positive_only)...")
        height_grid += _generate_layer(
            seed=seed + 1,
            layer_cfg=layer_cfg,
            base_coords_x=x_coords_base,
            base_coords_z=z_coords_base,
            cell_size=cell_size,
            scratch_buffer=scratch_buffers["a"],
        )

    # --- ЭТАП 2: Ограничитель уклона (сухая эрозия) на макро-слоях ---
    limiter_cfg = cfg.get("slope_limiter", {})
    if limiter_cfg.get("enabled", False):
        print("  -> Applying slope limiter (dry erosion) on macro-terrain...")
        max_angle_deg = float(limiter_cfg.get("max_angle_deg", 50.0))
        auto_iters = bool(limiter_cfg.get("auto_iterations", True))
        iters_cap = int(limiter_cfg.get("iterations_cap", 128))
        iters_manual = int(limiter_cfg.get("iterations", 16))

        g_max = math.tan(math.radians(max_angle_deg))
        # Осевой допустимый перепад: Δh_axis = (tan θ_max * s) / √2
        delta_axis = (g_max * cell_size) / math.sqrt(2.0)

        if auto_iters:
            # Оценка худшего перепада между соседями по осям
            diff_x = np.abs(height_grid[:, 1:] - height_grid[:, :-1]).max() if height_grid.shape[1] > 1 else 0.0
            diff_z = np.abs(height_grid[1:, :] - height_grid[:-1, :]).max() if height_grid.shape[0] > 1 else 0.0
            max_pair = float(max(diff_x, diff_z))
            # Сколько "попарных сдвигов" нужно, чтобы уложиться в порог
            iters_need = int(math.ceil(max_pair / max(delta_axis, 1e-9)))
            iterations = max(8, min(iters_need, iters_cap))  # нижняя граница — 8 проходов
        else:
            iterations = iters_manual

        _apply_slope_limiter(height_grid, g_max, cell_size, iterations)

    # --- ЭТАП 3: Средние и мелкие аддитивные детали (знаковые) ---
    if "erosion" in spectral_cfg:
        layer_cfg = dict(spectral_cfg["erosion"])
        layer_cfg["is_base"] = False
        print("  -> Generating layer: erosion...")
        height_grid += _generate_layer(
            seed=seed + 2,
            layer_cfg=layer_cfg,
            base_coords_x=x_coords_base,
            base_coords_z=z_coords_base,
            cell_size=cell_size,
            scratch_buffer=scratch_buffers["a"],
        )

    if "ground_details" in spectral_cfg:
        layer_cfg = dict(spectral_cfg["ground_details"])
        layer_cfg["is_base"] = False
        print("  -> Generating layer: ground_details...")
        height_grid += _generate_layer(
            seed=seed + 3,
            layer_cfg=layer_cfg,
            base_coords_x=x_coords_base,
            base_coords_z=z_coords_base,
            cell_size=cell_size,
            scratch_buffer=scratch_buffers["a"],
        )

    # --- ЭТАП 4: Высекание вершин (опционально) ---
    if "peak_carving" in spectral_cfg:
        # TODO: Реализовать при необходимости:
        #  1) нормализовать абсолютную высоту h_norm = h / max_height_m;
        #  2) построить маску m = smoothstep(th - s/2, th + s/2, h_norm);
        #  3) сгенерировать мелкий ridged-шум и добавить h += amp * noise * m.
        pass

    # --- ЭТАП 5: Глобальное сглаживание (если нужно) ---
    smoothing_passes = int(cfg.get("smoothing_passes", 0))
    if smoothing_passes > 0:
        sigma = 0.6 * smoothing_passes
        gaussian_filter(height_grid, sigma=sigma, output=scratch_buffers["b"], mode="reflect")
        height_grid = np.copy(scratch_buffers["b"])

    # --- ЭТАП 6: Финальные сдвиг/клип ---
    height_grid += float(cfg.get("base_height_m", 0.0))
    np.clip(height_grid, 0.0, float(cfg.get("max_height_m", 150.0)), out=height_grid)

    _print_range("height_final", height_grid)
    return height_grid.copy()
