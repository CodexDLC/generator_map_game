# ======================================================================
# Файл: game_engine_restructured/numerics/field_packet.py
# Назначение: Унифицированная упаковка "карта + метаданные".
# ======================================================================
from __future__ import annotations
import numpy as np
from typing import Any, Dict, Optional

Packet = Dict[str, Any]
SPACE_NORM = "norm01"
SPACE_METR = "meters"

def make_packet(
    data: np.ndarray,
    *,
    space: str = SPACE_NORM,     # "norm01" | "meters"
    ref_m: Optional[float] = None,
    amp_m: Optional[float] = None,
    bias_m: float = 0.0
) -> Packet:
    return {
        "data": np.asarray(data, dtype=np.float32),
        "space": space,
        "ref_m": float(ref_m) if ref_m is not None else None,
        "amp_m": float(amp_m) if amp_m is not None else None,
        "bias_m": float(bias_m),
    }

def is_packet(x: Any) -> bool:
    return isinstance(x, dict) and "data" in x and "space" in x

def get_data(x: Any) -> np.ndarray:
    if is_packet(x):
        return np.asarray(x["data"], dtype=np.float32)
    return np.asarray(x, dtype=np.float32)

def get_space(x: Any, default: str = SPACE_NORM) -> str:
    if is_packet(x):
        s = x.get("space") or default
        return s
    return default

def get_ref_m(x: Any, default: Optional[float] = None) -> Optional[float]:
    if is_packet(x):
        return x.get("ref_m") or x.get("amp_m") or default
    return default

def get_amp_m(x: Any, default: Optional[float] = None) -> Optional[float]:
    if is_packet(x):
        return x.get("amp_m") or default
    return default

def get_bias_m(x: Any) -> float:
    if is_packet(x):
        return float(x.get("bias_m") or 0.0)
    return 0.0

# --- Утилиты преобразований (без лишних копий массивов) ---

def to_meters(x: Any, fallback_ref_m: Optional[float] = None) -> np.ndarray:
    """
    Возвращает массив в метрах:
      - если вход уже meters — вернёт data (bias не применяем здесь);
      - если вход norm01 — умножим на ref_m (или fallback_ref_m).
    """
    a = get_data(x)
    space = get_space(x)
    if space == SPACE_METR:
        return a
    ref = get_ref_m(x, fallback_ref_m)
    if ref is None:
        raise ValueError("to_meters: ref_m is required for norm01 input")
    return a * float(ref)

def to_norm01(x: Any, fallback_ref_m: Optional[float] = None, clip: bool = True) -> np.ndarray:
    """
    Возвращает массив в [0..1]:
      - если вход norm01 — вернёт data (опц. клип);
      - если вход meters — поделим на ref_m (или fallback_ref_m).
    """
    a = get_data(x)
    space = get_space(x)
    if space == SPACE_NORM:
        if clip:
            return np.clip(a, 0.0, 1.0, out=np.empty_like(a))
        return a
    ref = get_ref_m(x, fallback_ref_m)
    if ref is None or ref == 0:
        raise ValueError("to_norm01: valid ref_m is required for meters input")
    out = a / float(ref)
    if clip:
        np.clip(out, 0.0, 1.0, out=out)
    return out
