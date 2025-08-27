from queue import Queue
from .tasks import run_in_thread
from worldgen_core.pipeline import generate_world
from worldgen_core.utils.window import extract_window

# безопасная прокладка для scatter: если нет реализации — тихо no-op
try:
    from worldgen_core.scatter import scatter_world as _scatter_impl
except Exception:  # ImportError, AttributeError и др.
    def _scatter_impl(*args, **kwargs):
        return  # заглушка

def generate(cfg):
    q = Queue()
    t = run_in_thread(generate_world, cfg, update_queue=q)
    return t, q

def extract(src_base, dst_base, origin_x, origin_y, width, height, chunk, copy_biomes=True):
    return run_in_thread(
        extract_window,
        src_base, dst_base, origin_x, origin_y, width, height, chunk, copy_biomes
    )

def scatter(*args, **kwargs):
    """Запускает worldgen_core.scatter.scatter_world(...) в фоне (или no-op, если нет реализации)."""
    return run_in_thread(_scatter_impl, *args, **kwargs)
