# ========================
# file: game_engine/core/preset/loader.py
# ========================
from __future__ import annotations
import os
import json
import copy
from typing import Any, Dict, Union, Mapping

from .defaults import DEFAULT_BASE_PRESET_V2
from .migrate import upgrade_to_v2
from .model import Preset
from .registry import resolve_preset_path
from .validators import validate_dict
from .version import CURRENT_PRESET_VERSION


# The one and only fully-resolved default preset dataclass.
# Lazily loaded on first `load_preset()` call to avoid import cycles.
DEFAULT_BASE_PRESET: Preset | None = None


def deep_merge(base: Dict[str, Any], overrides: Mapping[str, Any]) -> Dict[str, Any]:
    """Recursive dict merge. Lists/tuples are replaced, not merged element-wise."""
    out = copy.deepcopy(base)
    for k, v in overrides.items():
        if isinstance(v, Mapping) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _load_json_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_preset(
    source: Union[str, Dict[str, Any]], overrides: Mapping[str, Any] | None = None
) -> Preset:
    """Load a preset from id/path/dict, migrate to v2, merge with v2 defaults and apply overrides.

    Args:
        source: preset id (e.g., 'world/base_default'), or file path to JSON, or raw dict
        overrides: mapping of ad-hoc overrides (last layer)
    Returns:
        Preset (immutable dataclass) ready for use
    """
    if isinstance(source, str):
        if os.path.isfile(source):
            data = _load_json_file(source)
        else:
            # treat as id
            path = resolve_preset_path(source)
            data = _load_json_file(path)
    elif isinstance(source, dict):
        data = source
    else:
        raise TypeError("source must be str path/id or dict")

    data = upgrade_to_v2(data)

    # Merge with defaults and optional overrides
    merged = deep_merge(DEFAULT_BASE_PRESET_V2, data)
    if overrides:
        merged = deep_merge(merged, overrides)

    # Final version field
    merged["version"] = CURRENT_PRESET_VERSION

    # Validate
    validate_dict(merged)

    # Build dataclass
    preset = Preset(
        id=merged["id"],
        version=int(merged.get("version", CURRENT_PRESET_VERSION)),
        size=int(merged["size"]),
        cell_size=float(merged["cell_size"]),
        initial_load_radius=int(merged["initial_load_radius"]),
        region_size=int(merged["region_size"]),
        city_wall=dict(merged.get("city_wall", {})),
        elevation=dict(merged["elevation"]),
        terraform=dict(merged.get("terraform", {})),
        climate=dict(merged.get("climate", {})),
        slope_obstacles=dict(merged.get("slope_obstacles", {})),
        scatter=dict(merged.get("scatter", {})),
        obstacles=dict(merged.get("obstacles", {})),
        water=dict(merged.get("water", {})),
        height_q=dict(merged.get("height_q", {})),
        ports=dict(merged.get("ports", {})),
        fields=dict(merged.get("fields", {})),
        export=dict(merged.get("export", {})),
        pre_rules=dict(merged.get("pre_rules", {})),
    )

    # Publish DEFAULT_BASE_PRESET on first successful load of defaults to avoid import cycles
    global DEFAULT_BASE_PRESET
    if DEFAULT_BASE_PRESET is None:
        # Create it from DEFAULT_BASE_PRESET_V2 directly (already valid)
        validate_dict(DEFAULT_BASE_PRESET_V2)
        DEFAULT_BASE_PRESET = Preset(
            id=DEFAULT_BASE_PRESET_V2["id"],
            version=CURRENT_PRESET_VERSION,
            size=DEFAULT_BASE_PRESET_V2["size"],
            cell_size=DEFAULT_BASE_PRESET_V2["cell_size"],
            initial_load_radius=DEFAULT_BASE_PRESET_V2["initial_load_radius"],
            region_size=DEFAULT_BASE_PRESET_V2["region_size"],
            city_wall=dict(DEFAULT_BASE_PRESET_V2.get("city_wall", {})),
            elevation=dict(DEFAULT_BASE_PRESET_V2["elevation"]),
            terraform=dict(DEFAULT_BASE_PRESET_V2.get("terraform", {})),
            climate=dict(DEFAULT_BASE_PRESET_V2.get("climate", {})),
            slope_obstacles=dict(DEFAULT_BASE_PRESET_V2.get("slope_obstacles", {})),
            scatter=dict(DEFAULT_BASE_PRESET_V2.get("scatter", {})),
            obstacles=dict(DEFAULT_BASE_PRESET_V2.get("obstacles", {})),
            water=dict(DEFAULT_BASE_PRESET_V2.get("water", {})),
            height_q=dict(DEFAULT_BASE_PRESET_V2.get("height_q", {})),
            ports=dict(DEFAULT_BASE_PRESET_V2.get("ports", {})),
            fields=dict(DEFAULT_BASE_PRESET_V2.get("fields", {})),
            export=dict(DEFAULT_BASE_PRESET_V2.get("export", {})),
            pre_rules=dict(DEFAULT_BASE_PRESET_V2.get("pre_rules", {})),
        )

    return preset
