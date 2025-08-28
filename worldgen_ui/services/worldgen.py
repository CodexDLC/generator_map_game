from queue import Queue

from worldgen_core import generate_grid
from .tasks import run_in_thread
from worldgen_core.pipeline import generate_world
from worldgen_core.utils.window import extract_window

# безопасная прокладка для scatter: если нет реализации — тихо no-op


def generate(cfg):
    q = Queue()
    t = run_in_thread(generate_world, cfg, update_queue=q)
    return t, q

def extract(src_base, dst_base, origin_x, origin_y, width, height, chunk, copy_biomes=True):
    return run_in_thread(
        extract_window,
        src_base, dst_base, origin_x, origin_y, width, height, chunk, copy_biomes
    )

def generate_grid_sync(seed, width, height, out_dir, wall_chance): # <-- Добавлен wall_chance
    """Синхронный вызов генератора сеток."""
    return generate_grid(
        seed=seed,
        width=width,
        height=height,
        out_dir=out_dir,
        wall_chance=wall_chance # <-- Добавлен wall_chance
    )