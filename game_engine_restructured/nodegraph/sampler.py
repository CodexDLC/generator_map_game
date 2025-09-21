# sampler.py
from .stateless_rng import rnd01

def poisson_cells(world_rect_px, radius_px, layer_seed, max_tries=30):
    """world_rect_px=(x0,z0,size). Возвращает центры (x,z) в мировых пикселях."""
    x0,z0,S = world_rect_px
    cell = radius_px
    pts = []
    # пробегаем сетку клеток; решение принимать/масштаб/поворот — через rnd01
    for cz in range(z0, z0+S, cell):
        for cx in range(x0, x0+S, cell):
            r = rnd01(cx//cell, cz//cell, layer_seed)
            if r < 0.5:  # шанс 50% — настрой через параметр
                pts.append((cx + cell//2, cz + cell//2))
    return pts
