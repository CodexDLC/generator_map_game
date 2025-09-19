# game_engine_restructured/algorithms/terrain/terracing.py
from __future__ import annotations
import numpy as np
from typing import Any, Dict

# используем твой генератор шума
from game_engine_restructured.algorithms.terrain.terrain_helpers import generate_noise_layer


def _smoothstep(a: float, b: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - a) / (b - a + 1e-8), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _noise(seed: int, scale_tiles: float, octaves: int,
          x_coords: np.ndarray, z_coords: np.ndarray, cell_size: float) -> np.ndarray:
    """Удобная обёртка: отдаём шум в диапазоне [-1..1] при amp_m=1."""
    cfg = {
        "amp_m": 1.0,
        "scale_tiles": float(scale_tiles),
        "octaves": int(octaves),
        "ridge": False,
        "shaping_power": 1.0,
    }
    return generate_noise_layer(seed, cfg, x_coords, z_coords, cell_size)


def apply_terracing_effect(
    height_grid: np.ndarray,          # (H, W) высоты в метрах
    mask_strength: np.ndarray,        # (H, W) 0..1 где террасировать
    cfg: Dict[str, Any],
    *,                                 # ↓↓↓ ИМЕНОВАННЫЕ аргументы (как у тебя вызывается)
    seed: int = 0,
    x_coords: np.ndarray | None = None,
    z_coords: np.ndarray | None = None,
    cell_size: float = 1.0
) -> np.ndarray:
    """
    Симметричное террасирование с рандомизацией.
    Совместимо с вызовом из terrain.py (seed/x_coords/z_coords/cell_size).
    Включены детальные print-логи.
    """
    if not bool(cfg.get("enabled", True)):
        print("[Terrace] disabled → skip")
        return height_grid

    step_h = float(cfg.get("step_height_m", 60.0))
    ledge_ratio = float(cfg.get("ledge_ratio", 0.7))
    strength_m = float(cfg.get("strength_m", 10.0))
    rnd: Dict[str, Any] = cfg.get("randomization", {}) or {}

    # --- Сводка входа
    print(f"[TerraceCfg] step={step_h:.2f}m ledge={ledge_ratio:.2f} strength={strength_m:.2f}m "
          f"| rnd={ {k: rnd.get(k) for k in ('phase_jitter_m','phase_scale_tiles','step_jitter_ratio','step_scale_tiles','ledge_jitter','ledge_scale_tiles','break_threshold','break_scale_tiles','break_octaves','height_step_gain','curvature_fade')} }")
    print(f"[Terrace] input height: min={height_grid.min():.2f} max={height_grid.max():.2f}")
    print(f"[Terrace] mask>0.4 coverage: {float((mask_strength>0.4).mean()*100.0):.1f}%")

    H, W = height_grid.shape
    # ---------- 1) Джиттер шага (разное число полок по склонам) ----------
    step_ratio = float(rnd.get("step_jitter_ratio", 0.0))
    step_scale = float(rnd.get("step_scale_tiles", 2500.0))
    height_step_gain = float(rnd.get("height_step_gain", 0.0))

    if step_ratio != 0.0:
        n_step = _noise(seed + 11, step_scale, 2, x_coords, z_coords, cell_size)  # [-1..1]
    else:
        n_step = np.zeros_like(height_grid)

    # нормировка высоты в рамках региона, чтобы поднять шаг к верху
    h_min, h_max = float(height_grid.min()), float(height_grid.max())
    h_norm = (height_grid - h_min) / (h_max - h_min + 1e-8)

    step_local = step_h * (1.0 + step_ratio * n_step) * (1.0 + height_step_gain * h_norm)
    step_local = np.clip(step_local, 0.33 * step_h, 3.0 * step_h)

    # ---------- 2) Фазовый джиттер (сдвиг колец по высоте) ----------
    phase_jitter_m = float(rnd.get("phase_jitter_m", 0.0))
    phase_scale = float(rnd.get("phase_scale_tiles", 2000.0))
    if phase_jitter_m != 0.0:
        n_phase = _noise(seed + 17, phase_scale, 3, x_coords, z_coords, cell_size)  # [-1..1]
    else:
        n_phase = 0.0

    h2 = height_grid + phase_jitter_m * n_phase

    # ---------- 3) Джиттер ширины полки ----------
    ledge_jitter = float(rnd.get("ledge_jitter", 0.0))
    ledge_scale = float(rnd.get("ledge_scale_tiles", 3000.0))
    if ledge_jitter != 0.0:
        n_ledge = _noise(seed + 23, ledge_scale, 2, x_coords, z_coords, cell_size)  # [-1..1]
        ledge_local = np.clip(ledge_ratio * (1.0 + ledge_jitter * n_ledge), 0.5, 0.9)
    else:
        ledge_local = np.full_like(height_grid, np.clip(ledge_ratio, 0.05, 0.95))

    # ---------- 4) Фаза и симметричная деформация ----------
    phase = np.mod(h2, step_local) / np.maximum(step_local, 1e-6)  # [0..1)
    u = np.where(phase < ledge_local, phase / np.maximum(ledge_local, 1e-6),
                 (phase - ledge_local) / np.maximum(1.0 - ledge_local, 1e-6))       # [0..1]
    bell = 1.0 - (2.0 * u - 1.0) ** 2                                              # 0..1
    sign = np.where(phase < ledge_local, 1.0, -0.75)                                # «обрыв» слабее
    deformation = sign * bell * strength_m                                          # метры

    # Диагностика фазы и сырой деформации
    mount_area = (mask_strength > 0.4)
    if mount_area.any():
        p5, p50, p95 = np.percentile(phase[mount_area], [5, 50, 95])
        print(f"[Terrace] phase@mount p5={p5:.2f} p50={p50:.2f} p95={p95:.2f} span={p95-p5:.2f}")
        d = deformation[mount_area]
    else:
        d = deformation
        print("[Terrace] phase@mount: <no area>")
    print(f"[Terrace] deform raw:  min={d.min():.2f} max={d.max():.2f} mean={d.mean():.2f} "
          f"|d|>0.5m={float((np.abs(d)>0.5).mean()*100.0):.1f}%")

    # ---- BREAK SEGMENTS (адаптивный порог + soft gate + утолщение) ----
    rnd = cfg.get("randomization", {}) or {}
    break_scale = float(rnd.get("break_scale_tiles", 1400.0))
    break_oct = int(rnd.get("break_octaves", 1))
    # генерим breaking в [0..1], с минимумом 0.35 чтобы не глушить в ноль
    n_break = _noise(seed + 31, break_scale, break_oct, x_coords, z_coords, cell_size)  # [-1..1]
    breaking = np.clip(0.5 + 0.5 * n_break, 0.35, 1.0)

    # целевая доля «включённых» сегментов на горных участках (0.0..1.0)
    target_cov = float(rnd.get("break_target_coverage", 0.40))  # 40% по умолч.
    mount_area = (mask_strength > 0.4)
    if mount_area.any():
        thr = float(np.quantile(breaking[mount_area], 1.0 - target_cov))
    else:
        thr = float(np.quantile(breaking, 1.0 - target_cov))

    hard = (breaking > thr).astype(np.float32)

    # утолщение сегментов на r пикселей (дешёвая дилатация через np.roll)
    r = int(rnd.get("break_thicken_radius", 2))  # 0 = без утолщения
    if r > 0:
        base = hard.copy()
        for dz in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx == 0 and dz == 0:
                    continue
                hard = np.maximum(hard, np.roll(np.roll(base, dz, axis=0), dx, axis=1))

    # soft-ворота: вне сегментов не 0, а небольшой коэффициент
    keep_off = float(rnd.get("break_keep_off", 0.25))  # 25% амплитуды снаружи
    gate = np.where(hard > 0.5, 1.0, keep_off)

    # применяем к деформации (если у тебя ещё есть curvature_mask — умножай её ДО gate)
    d_fin = deformation * np.clip(mask_strength, 0.0, 1.0) * gate

    # диагностика
    if mount_area.any():
        cov = float((hard[mount_area] > 0.5).mean() * 100.0)
    else:
        cov = float((hard > 0.5).mean() * 100.0)
    print(f"[Terrace] break target={target_cov * 100:.0f}% → actual={cov:.1f}% thr={thr:.2f} "
          f"| breaking[min={breaking.min():.2f} max={breaking.max():.2f}]")

    # === FINALIZE APPLY (всегда формируем out) ===
    if 'gate' not in locals():
        gate = 1.0

    # если ранее d_fin не собрали — соберём базовый вариант
    if 'd_fin' not in locals():
        d_fin = deformation * np.clip(mask_strength, 0.0, 1.0) * gate

    out = height_grid + d_fin

    # короткая диагностика перед возвратом
    dh = out - height_grid
    print(
        f"[Terrace][OK] Δmax={dh.max():.2f} Δmean={dh.mean():.2f} |Δ|>0.5m={float((np.abs(dh) > 0.5).mean() * 100.0):.1f}%")

    return out
