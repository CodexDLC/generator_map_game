# ========================
# file: game_engine/core/preset/defaults.py
# ========================
from __future__ import annotations
from typing import Any, Dict
from .version import CURRENT_PRESET_VERSION

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model import Preset

# Strict python-dict mirror of the JSON we agreed on as v2 defaults
DEFAULT_BASE_PRESET_V2: Dict[str, Any] = {
    "id": "world/base_default",
    "version": CURRENT_PRESET_VERSION,
    "size": 256,
    "cell_size": 1.0,
    "initial_load_radius": 1,
    "region_size": 3,
    "elevation": {
        "enabled": True,
        "max_height_m": 150.0,
        "shaping_power": 1.02,
        "smoothing_passes": 1,
        "quantization_step_m": 0.0,
        "spectral": {
            "continents": {
                "scale_tiles": 8000,
                "amp_m": 120.0,
                "ridge": True,
                "octaves": 2,
            },
            "hills": {"scale_tiles": 1400, "amp_m": 40.0, "octaves": 2},
            "detail": {"scale_tiles": 150, "amp_m": 7.0, "octaves": 1},
        },
        "warp": {"scale_tiles": 4000, "strength_m": 200.0},
    },
    "terraform": {
        "enabled": True,
        "rules": [
            {
                "enabled": True,
                "type": "remap",
                "comment": "Создаем высокие плато",
                "noise_from": 0.8,
                "noise_to": 0.9,
                "remap_to_from": 0.85,
                "remap_to_to": 1.0,
            },
            {
                "enabled": False,
                "type": "flatten",
                "comment": "Идеально плоские соляные озера (выкл)",
                "noise_from": 0.12,
                "noise_to": 0.15,
                "target_noise": 0.10,
            },
        ],
    },
    "climate": {
        "enabled": False,
        "temperature": {
            "enabled": False,
            "base_c": 18.0,
            "latitude_axis": "Z",
            "gradient_c_per_km": -0.02,
            "noise_scale_tiles": 9000,
            "noise_amp_c": 6.0,
            "lapse_rate_c_per_m": -0.0065,
            "clamp_c": [-15.0, 35.0],
        },
        "humidity": {
            "enabled": False,
            "base": 0.45,
            "noise_scale_tiles": 10000,
            "noise_amp": 0.35,
            "orographic": {
                "enabled": False,
                "wind_source": "global",
                "wind_deg": 260,
                "upwind_gain": 0.25,
                "leeward_loss": 0.20,
            },
            "clamp": [0.0, 1.0],
        },
        "wind": {
            "enabled": False,
            "mode": "global",
            "deg": 260,
            "variability_deg": 20,
            "variability_scale_tiles": 12000,
        },
    },
    "scatter": {
        "enabled": True,
        "groups": {"noise_scale_tiles": 384.0, "threshold": 0.48},
        "details": {"noise_scale_tiles": 12.0, "threshold": 0.45},
        "thinning": {"enabled": True, "min_distance": 3},
    },
    "slope_obstacles": {"enabled": True, "angle_threshold_deg": 45, "band_cells": 3},
    "export": {
        "palette": {
            "ground": "#7a9e7a",
            "obstacle": "#698669",
            "water": "#3573b8",
            "road": "#d2b48c",
            "slope": "#9aa0a6",
            "void": "#00000000",
            "wall": "#808080",
            "bridge": "#b8b8b8",
            "sand": "#e0cda8",
            "forest_ground": "#6b8f6b",  # добавлен цвет для forest_ground
        },
        "thick": True,
    },
    "pre_rules": {
        "enabled": False,
        "south_ocean": {
            "enabled": False,
            "cz_min_ocean": 8,
            "initial_depth_factor": 0.1,
            "max_depth_factor": 0.33,
            "deepen_range_chunks": 3,
        },
        "cz0_coast": {
            "enabled": False,
            "depth_min_tiles": 4,
            "depth_max_tiles": 7,
            "smooth_passes": 4,
        },
    },
    # legacy blocks kept for compat (neutralized)
    "obstacles": {"density": 0.12, "min_blob": 8, "max_blob": 64},
    "water": {"density": 0.0, "lake_chance": 0.0},
    "height_q": {"scale": 0.1},
    "ports": {"min": 2, "max": 4, "edge_margin": 3},
    "fields": {},
    "city_wall": {},
}


# A ready-to-use Preset object built from defaults via loader in __init__ time
# (imported by package __init__) will be created in loader after validation
DEFAULT_BASE_PRESET: "Preset"  # populated in loader to avoid circular import
