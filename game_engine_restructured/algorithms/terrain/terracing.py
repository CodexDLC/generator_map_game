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

    # ---------- 5) Break-mask (рвём кольца на сегменты) и «амплитудный» breaking ----------
    break_thr = rnd.get("break_threshold", None)
    breaking = None
    break_mask = None
    if break_thr is not None:
        break_scale = float(rnd.get("break_scale_tiles", 1200.0))
        break_oct = int(rnd.get("break_octaves", 1))
        n_break = _noise(seed + 31, break_scale, break_oct, x_coords, z_coords, cell_size)  # [-1..1]
        breaking = 0.5 + 0.5 * n_break                                   # 0..1
        breaking = np.clip(breaking, 0.35, 1.0)                           # не гасим в ноль
        break_mask = (breaking > float(break_thr)).astype(np.float32)     # 0/1

        cov = float((break_mask[mount_area] > 0.5).mean()*100.0) if mount_area.any() else float((break_mask>0.5).mean()*100.0)
        print(f"[Terrace] break coverage: {cov:.1f}% thr={break_thr} "
              f"| breaking[min={breaking.min():.2f} max={breaking.max():.2f}]")
    else:
        # Если порога нет — используем только мягкий «breaking» как амплитудный множитель 0.5..1.0
        breaking = None
        print("[Terrace] break: OFF")

    # ---------- 6) Кривизна (ослабить ступени на выпуклых гребнях) ----------
    curvature_fade = float(rnd.get("curvature_fade", 0.0))
    if curvature_fade > 0.0:
        gy, gx = np.gradient(height_grid, cell_size)
        gyy, _ = np.gradient(gy, cell_size)
        _, gxx = np.gradient(gx, cell_size)
        curvature = gxx + gyy                   # >0 на гребнях, <0 в лощинах
        concave_mask = _smoothstep(0.0, curvature_fade, -curvature)  # 1 в лощинах → держим ступени
    else:
        concave_mask = 1.0

    # ---------- 7) Собираем финальную деформацию ----------
    d_fin = deformation * concave_mask * np.clip(mask_strength, 0.0, 1.0)
    if breaking is not None:
        d_fin = d_fin * breaking
    if break_mask is not None:
        d_fin = d_fin * break_mask

    df = d_fin[mount_area] if mount_area.any() else d_fin
    print(f"[Terrace] deform final: min={df.min():.2f} max={df.max():.2f} mean={df.mean():.2f} "
          f"|d|>0.5m={float((np.abs(df)>0.5).mean()*100.0):.1f}%")

    # ---------- 8) Применяем ----------
    out = height_grid + d_fin
    dh = out - height_grid
    print(f"[Terrace] heights: before[min={height_grid.min():.2f} max={height_grid.max():.2f}] "
          f"after[min={out.min():.2f} max={out.max():.2f}] "
          f"Δmax={dh.max():.2f} Δmean={dh.mean():.2f} |Δ|>0.5m={float((np.abs(dh)>0.5).mean()*100.0):.1f}%")

    return out
