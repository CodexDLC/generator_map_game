import logging
from pathlib import Path
import uuid

from worldgen_core.grid_utils.topology import open_ratio, bump_open_to, largest_component_only, add_border, bfs_reachable, carve_l
from worldgen_core.grid_utils.features import add_water, pick_entry_exit
from worldgen_core.grid_utils.export import build_json, save_json, render_png
from worldgen_core.grid_utils.cellular import make_noise_grid, smooth_cellular
from worldgen_core.grid_utils.core import GenParams, init_rng, PASSABLE_DEFAULT


def generate_grid(seed, width, height, out_dir, wall_chance):
    """
    v0: пещерная генерация + вода + вход/выход.
    Возвращает {"png":..., "json":..., "seed":..., "map_id":...}
    """
    params = GenParams(seed=seed, w=width, h=height, wall_chance=wall_chance)
    rng, actual_seed = init_rng(params.seed)
    params.seed = actual_seed

    # 1) шум + сглаживание
    grid = make_noise_grid(rng, params.w, params.h, params.wall_chance)
    grid = smooth_cellular(grid, steps=5)

    # 2) связность → рамка → вода
    largest_component_only(grid)
    add_border(grid)
    add_water(grid, params.seed, params.water_scale, params.water_thr)

    # 3) контроль открытости (после воды)
    if open_ratio(grid, PASSABLE_DEFAULT) < params.open_min:
        bump_open_to(grid, params.open_min, rng, PASSABLE_DEFAULT)

    # 4) вход/выход + гарантировать путь
    entry, exit_pos = pick_entry_exit(grid, rng)
    start_in, goal_in = (1, entry[1]), (params.w - 2, exit_pos[1])
    if not bfs_reachable(grid, start_in, goal_in, PASSABLE_DEFAULT):
        logging.info("Пути нет — режем L-коридор.")
        carve_l(grid, start_in, goal_in)

    # 5) экспорт
    out = Path(out_dir)
    map_id = uuid.uuid4().hex
    data = build_json(grid, entry, exit_pos, params, map_id=map_id)
    json_path = save_json(data, out)
    png_path = render_png(grid, entry, exit_pos, out, tile_px=16)

    logging.info(f"OK: JSON→ {json_path.name}, PNG→ {png_path.name}")
    return {
        "png": str(png_path.resolve()),
        "json": str(json_path.resolve()),
        "seed": params.seed,
        "map_id": map_id,
    }
