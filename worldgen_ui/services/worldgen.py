# worldgen_ui/services/worldgen.py
from worldgen_core import generate_grid

_ALLOWED = {"seed","width","height","out_dir","wall_chance",
            "open_min","border_mode","border_outer_cells",
            "validate_for","allow_no_base_path","tile_rules"}

def generate_grid_sync(seed, width, height, out_dir, wall_chance, **kwargs):
    return generate_grid(
        seed=seed, width=width, height=height, out_dir=out_dir, wall_chance=wall_chance, **kwargs
    )