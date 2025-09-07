# ========================
# file: game_engine/core/preset/migrate.py
# ========================
from __future__ import annotations
from typing import Any, Dict
import copy
import logging
from .version import CURRENT_PRESET_VERSION


logger = logging.getLogger(__name__)


def upgrade_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
    """Upgrade a v1-like preset dict to v2 schema.


    Heuristics:
    - move elevation.terraform -> root terraform
    - drop elevation.sea_level_m (ocean disabled), warn once
    - convert elevation.noise_scale_tiles into spectral estimates
    - ensure climate skeleton exists but disabled
    """
    d = copy.deepcopy(data)
    ver = int(d.get("version", 1))
    if ver >= 2:
        return d

    elv = d.get("elevation", {}) or {}

    # Move terraform from elevation to root
    if "terraform" in elv and "terraform" not in d:
        d["terraform"] = elv.pop("terraform")

    # Remove sea_level_m (we don't use global ocean now)
    if "sea_level_m" in elv:
        elv.pop("sea_level_m", None)
        logger.warning(
            "[preset.migrate] Dropped elevation.sea_level_m during v1→v2 migration (ocean disabled)."
        )

    # Map a single noise scale to multi-spectral (rough heuristic)
    old_scale = elv.pop("noise_scale_tiles", None)
    spectral = elv.get("spectral")
    if spectral is None:
        spectral = {}
    elv["spectral"] = spectral
    if not spectral:
        # Provide defaults based on old scale or fallback numbers
        if old_scale is None:
            continents_scale = 8000
            hills_scale = 1400
            detail_scale = 150
        else:
            # Old scale was the "mid" hill scale; build others around it
            hills_scale = max(200.0, float(old_scale))
            continents_scale = max(2000.0, hills_scale * 6.0)
            detail_scale = max(50.0, hills_scale / 8.0)
        spectral.update(
            {
                "continents": {
                    "scale_tiles": continents_scale,
                    "amp_m": 120.0,
                    "ridge": True,
                    "octaves": 2,
                },
                "hills": {"scale_tiles": hills_scale, "amp_m": 40.0, "octaves": 2},
                "detail": {"scale_tiles": detail_scale, "amp_m": 7.0, "octaves": 1},
            }
        )

    # Ensure warp exists
    elv.setdefault("warp", {"scale_tiles": 4000, "strength_m": 200.0})

    # Ensure other elevation defaults exist (non-destructive)
    elv.setdefault("max_height_m", 150.0)
    elv.setdefault("shaping_power", 1.02)
    elv.setdefault("smoothing_passes", 1)
    elv.setdefault("quantization_step_m", 0.0)

    d["elevation"] = elv

    # Root terraform default
    d.setdefault("terraform", {"enabled": False, "rules": []})

    # Climate skeleton (disabled)
    d.setdefault(
        "climate",
        {
            "enabled": False,
            "temperature": {"enabled": False},
            "humidity": {"enabled": False, "orographic": {"enabled": False}},
            "wind": {"enabled": False},
        },
    )

    # Mark upgraded version
    d["version"] = CURRENT_PRESET_VERSION
    return d
