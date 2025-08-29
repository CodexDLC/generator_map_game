from __future__ import annotations

import uuid
import logging
from pathlib import Path

from archive.grid_utils.core import GenParams, TILE, init_rng
from archive.grid_utils import make_noise_grid, smooth_cellular
from archive.grid_utils.terrain import paint_road_on_path, apply_biomes
from engine.worldgen_core.grid_alg.topology import (
    largest_component_only,
    add_border,
    a_star_abilities,
    carve_l,
    fill_small_voids,
    widen_corridors,
    carve_path_weighted,
)
from archive.grid_utils.features import add_water, gen_rooms_map, carve_room_at
from archive.grid_utils.export import build_json_data, save_json, render_png_preview

log = logging.getLogger(__name__)


def _pick_entry_exit(
    grid: list[list[int]],
    border_layers: int = 1,
) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    h, w = len(grid), len(grid[0])
    inner_l = 1
    inner_r = max(0, w - 2)

    left_candidates = [y for y in range(1, h - 1) if grid[y][inner_l] == TILE["FLOOR"]]
    right_candidates = [y for y in range(1, h - 1) if grid[y][inner_r] == TILE["FLOOR"]]

    ey = left_candidates[len(left_candidates) // 2] if left_candidates else h // 2
    xy = right_candidates[-1] if right_candidates else h // 2

    layers = max(1, min(border_layers, w))
    for x in range(0, min(layers, w)):
        grid[ey][x] = TILE["FLOOR"]
    for x in range(max(0, w - layers), w):
        grid[xy][x] = TILE["FLOOR"]

    return (0, ey, 0), (w - 1, xy, 0)


def generate_grid(seed, width, height, out_dir, wall_chance, **kwargs):
    rng, actual_seed = init_rng(seed)
    params = GenParams(
        seed=actual_seed,
        w=width,
        h=height,
        wall_chance=float(wall_chance),
    )

    # UI → params
    params.open_min = float(kwargs.get("open_min", params.open_min))
    params.border_mode = kwargs.get("border_mode", params.border_mode)
    params.border_outer_cells = int(kwargs.get("border_outer_cells", params.border_outer_cells))
    params.validate_for = tuple(kwargs.get("validate_for", params.validate_for))
    params.allow_no_base_path = bool(kwargs.get("allow_no_base_path", params.allow_no_base_path))
    if "tile_rules" in kwargs and isinstance(kwargs["tile_rules"], dict):
        params.tile_rules = kwargs["tile_rules"]

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Этап 1: базовая сетка (cave/rooms)
    mode = str(kwargs.get("mode", getattr(params, "mode", "cave"))).lower()
    params.mode = mode
    if mode == "rooms":
        grid = gen_rooms_map(
            rng=rng, w=params.w, h=params.h,
            rooms_cfg=kwargs.get("rooms", {}),
            corridor_cfg=kwargs.get("corridor", {}),
        )
    else:
        grid = make_noise_grid(rng, params.w, params.h, params.wall_chance)
        grid = smooth_cellular(grid, steps=5)

    # Этап 2: связность и мелкие фиксы
    largest_component_only(grid)
    fill_small_voids(grid, max_area=int(params.w * params.h * 0.01))
    widen_corridors(grid, iterations=1)

    # Этап 3: бордер
    add_border(grid, params.border_mode, params.border_outer_cells)

    # Этап 4: вход/выход, залы у ворот, сухой путь
    entry, exit_pos = _pick_entry_exit(grid, params.border_outer_cells)
    start_in = (1, entry[1])
    goal_in = (params.w - 2, exit_pos[1])

    gate = kwargs.get("gate_room", {}) or {}
    rw = int(gate.get("w", 7))
    rh = int(gate.get("h", 7))
    avoid: set[tuple[int, int]] = set()
    avoid |= carve_room_at(grid, start_in[0], start_in[1], rw, rh)
    avoid |= carve_room_at(grid, goal_in[0], goal_in[1], rw, rh)

    path = carve_path_weighted(grid, start_in, goal_in, width=3, wall_cost=4)
    if path is None:
        carve_l(grid, start_in, goal_in)
        path = a_star_abilities(grid, start_in, goal_in, set(), params.tile_rules)

    avoid |= set(path)
    for x, y in list(path):
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < params.w and 0 <= ny < params.h:
                avoid.add((nx, ny))

    # Этап 5: вода (deep) после avoid
    deep_cfg = (kwargs.get("water") or {}).get("deep") or {}
    deep_scale = float(deep_cfg.get("scale", params.water_scale))
    deep_density = float(deep_cfg.get("density", 0.06))
    deep_thr = deep_cfg.get("threshold")
    add_water(grid, params.seed, deep_scale, target_density=deep_density, threshold=deep_thr, avoid=avoid)

    # --- Этап 5.1: дорога по гарантированному пути ---
    road_width = int((kwargs.get("biomes") or {}).get("road_width", 3))
    paint_road_on_path(grid, path, width=road_width)

    # --- Этап 5.2: биомы по весам ---
    biome_cfg = (kwargs.get("biomes") or {})
    biome_weights = biome_cfg.get("weights") or {"grass": 0.45, "forest": 0.30, "mountain": 0.15}
    safe_radius = int(biome_cfg.get("safe_radius_gate", 3))
    apply_biomes(
        grid,
        seed=params.seed,
        weights=biome_weights,
        safe_centers=[start_in, goal_in],  # залы у входа/выхода
        safe_radius=safe_radius,
        no_mountain_in_necks=bool(biome_cfg.get("no_mountain_in_necks", True)),
    )


    # Этап 6: экспорт
    map_id = str(uuid.uuid4())

    data = build_json_data(
        grid=grid,
        params=params,
        entry=entry,
        exit_pos=exit_pos,
        map_id=map_id,
        encoding=kwargs.get("encoding", "rle_rows_v1"),
    )

    per_dir = bool(kwargs.get("per_map_dir", True))
    png_on = bool(((kwargs.get("export") or {}).get("preview_png", True)))

    # ← пишем JSON через helper
    json_path = save_json(
        data=data,
        out_dir=out_path,
        map_id=map_id,
        compact=True,
        per_map_dir=per_dir,
        filename="map.json",
    )

    png_path = None
    if png_on:
        png_path = render_png_preview(
            grid, entry, exit_pos, out_path, map_id,
            per_map_dir=per_dir, filename="preview.png", tile_px=12
        )

    return {
        "png": str(png_path or ""),
        "json": str(json_path),
        "seed": actual_seed,
        "map_id": map_id,
    }