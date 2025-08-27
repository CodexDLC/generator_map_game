def is_int(s: str) -> bool:
    try:
        int(s)
        return True
    except Exception:
        return False

def is_float(s: str) -> bool:
    try:
        float(s)
        return True
    except Exception:
        return False

def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))
