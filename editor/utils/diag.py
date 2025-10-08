# editor/utils/diag.py
import logging
import numpy as np

logger = logging.getLogger(__name__)


def diag_array(arr: np.ndarray, name: str = "array"):
    """
    Выводит в DEBUG-лог детальную диагностическую информацию о NumPy массиве.
    """
    if not isinstance(arr, np.ndarray):
        logger.debug(f"DIAG {name}: Not a NumPy array (type: {type(arr).__name__})")
        return
    try:
        mn = float(np.min(arr))
        mx = float(np.max(arr))
        mean = float(np.mean(arr))
        has_nan = bool(np.isnan(arr).any())
        has_inf = bool(np.isinf(arr).any())

        logger.debug(
            f"DIAG {name}: shape={arr.shape}, dtype={arr.dtype}, "
            f"min={mn:.4f}, max={mx:.4f}, mean={mean:.4f}, "
            f"has_nan={has_nan}, has_inf={has_inf}"
        )
    except Exception as e:
        logger.error(f"DIAG {name}: Failed to get stats - {e}")