# editor/system_utils.py
import psutil

def get_system_memory_gb() -> tuple[float, float]:
    """Возвращает (общий, доступный) объем ОЗУ в ГБ."""
    try:
        mem = psutil.virtual_memory()
        total = mem.total / (1024 ** 3)
        available = mem.available / (1024 ** 3)
        return total, available
    except Exception:
        return 0.0, 0.0

def get_recommended_max_map_size() -> int:
    """Дает рекомендацию по макс. размеру карты на основе общего объема ОЗУ."""
    total_ram, _ = get_system_memory_gb()
    if total_ram < 8:
        return 2048  # Для систем < 8 ГБ
    if total_ram < 16:
        return 4096  # Для систем < 16 ГБ
    if total_ram < 32:
        return 8192  # Для систем < 32 ГБ
    return 16384 # Для систем >= 32 ГБ