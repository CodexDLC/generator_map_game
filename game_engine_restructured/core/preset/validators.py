# ========================
# file: game_engine/core/preset/validators.py
# ========================
from __future__ import annotations
from typing import Any, Dict
from .errors import ValidationError
from ..constants import SURFACE_KINDS


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValidationError(msg)


def validate_dict(cfg: Dict[str, Any]) -> None:
    """Basic, fairly conservative validation for v2 preset dicts.

    Raises ValidationError on the first failing check.
    """
    # Basic required fields
    _require(
        isinstance(cfg.get("id"), str) and cfg["id"],
        "Preset.id must be non-empty string",
    )
    _require(int(cfg.get("size", 0)) >= 8, "Preset.size must be >= 8")
    _require(float(cfg.get("cell_size", 0.0)) > 0.0, "Preset.cell_size must be > 0")
    _require(
        int(cfg.get("initial_load_radius", 0)) >= 0, "initial_load_radius must be >= 0"
    )
    _require(int(cfg.get("region_size", 0)) >= 1, "region_size must be >= 1")

    # Elevation (v2)
    elv = dict(cfg.get("elevation", {}))
    _require(
        elv.get("enabled", True) is True,
        "elevation.enabled must be True for Terrain3D mode",
    )
    for key in ("max_height_m", "shaping_power", "quantization_step_m"):
        _require(float(elv.get(key, 0.0)) >= 0.0, f"elevation.{key} must be >= 0")
    _require(
        int(elv.get("smoothing_passes", 0)) >= 0,
        "elevation.smoothing_passes must be >= 0",
    )

    spectral = dict(elv.get("spectral", {}))
    for layer in ("continents", "hills", "detail"):
        _require(layer in spectral, f"elevation.spectral.{layer} is required")
        L = dict(spectral[layer])
        _require(
            float(L.get("scale_tiles", 0.0)) > 0.0,
            f"elevation.spectral.{layer}.scale_tiles must be > 0",
        )
        _require(
            float(L.get("amp_m", 0.0)) >= 0.0,
            f"elevation.spectral.{layer}.amp_m must be >= 0",
        )

    warp = dict(elv.get("warp", {}))
    _require(
        float(warp.get("scale_tiles", 0.0)) > 0.0,
        "elevation.warp.scale_tiles must be > 0",
    )
    _require(
        float(warp.get("strength_m", 0.0)) >= 0.0,
        "elevation.warp.strength_m must be >= 0",
    )

    # Terraform
    tf = dict(cfg.get("terraform", {}))
    if tf.get("enabled", False):
        rules = list(tf.get("rules", []))
        for i, r in enumerate(rules):
            if not r.get("enabled", False):
                continue

            t = r.get("type")
            _require(
                t in ("remap", "flatten"),
                f"terraform.rules[{i}].type must be 'remap' or 'flatten'",
            )
            for k in ("noise_from", "noise_to"):
                v = float(r.get(k, 0.0))
                _require(0.0 <= v <= 1.0, f"terraform.rules[{i}].{k} must be in [0,1]")
            if t == "remap":
                for k in ("remap_to_from", "remap_to_to"):
                    v = float(r.get(k, 0.0))
                    _require(
                        0.0 <= v <= 1.0, f"terraform.rules[{i}].{k} must be in [0,1]"
                    )
            if t == "flatten":
                v = float(r.get("target_noise", 0.0))
                _require(
                    0.0 <= v <= 1.0,
                    f"terraform.rules[{i}].target_noise must be in [0,1]",
                )

    # Scatter
    sc = dict(cfg.get("scatter", {}))
    if sc.get("enabled", False):
        for sect in ("groups", "details"):
            S = dict(sc.get(sect, {}))
            _require(
                float(S.get("noise_scale_tiles", 0.0)) > 0.0,
                f"scatter.{sect}.noise_scale_tiles must be > 0",
            )
            thr = float(S.get("threshold", 0.0))
            _require(0.0 <= thr <= 1.0, f"scatter.{sect}.threshold must be in [0,1]")
        th = dict(sc.get("thinning", {}))
        if th.get("enabled", False):
            _require(
                float(th.get("min_distance", 0.0)) >= 0.0,
                "scatter.thinning.min_distance must be >= 0",
            )

    # Palette
    pal = dict(cfg.get("export", {}).get("palette", {}))

    # Минимальный набор, без которого визуализация точно сломается
    REQUIRED_SURFACE_COLORS = ("ground", "obstacle", "water", "road", "slope")
    for k in REQUIRED_SURFACE_COLORS:
        _require(k in pal, f"export.palette must contain color for surface '{k}'")
        col = str(pal[k])
        _require(
            col.startswith("#"),
            f"export.palette['{k}'] must be hex like '#RRGGBB' or '#AARRGGBB'",
        )

    for k in SURFACE_KINDS:
        if k in REQUIRED_SURFACE_COLORS or k == "void":
            continue
        if k in pal:
            col = str(pal[k])
            _require(
                col.startswith("#"),
                f"export.palette['{k}'] must be hex like '#RRGGBB' or '#AARRGGBB'",
            )

    # Legacy sanity checks (kept permissive)
    obs = dict(cfg.get("obstacles", {}))
    if obs:
        od = float(obs.get("density", 0.0))
        _require(0.0 <= od <= 1.0, "obstacles.density must be in [0,1]")
        mn = int(obs.get("min_blob", 1))
        mx = int(obs.get("max_blob", mn))
        _require(1 <= mn <= mx, "obstacles.min_blob <= max_blob and >= 1")

    wat = dict(cfg.get("water", {}))
    if wat:
        wd = float(wat.get("density", 0.0))
        _require(0.0 <= wd <= 1.0, "water.density must be in [0,1]")
        lc = float(wat.get("lake_chance", 0.0))
        _require(0.0 <= lc <= 1.0, "water.lake_chance must be in [0,1]")

    hq = dict(cfg.get("height_q", {}))
    if hq:
        _require(float(hq.get("scale", 0.1)) > 0.0, "height_q.scale must be > 0")

    ports = dict(cfg.get("ports", {}))
    if ports:
        pmin = int(ports.get("min", 1))
        pmax = int(ports.get("max", max(1, pmin)))
        _require(
            1 <= pmin <= pmax <= 4, "ports.min/max must satisfy 1 <= min <= max <= 4"
        )
        em = int(ports.get("edge_margin", 0))
        _require(
            0 <= em < int(cfg["size"]) // 2,
            "ports.edge_margin must be >=0 and < size/2",
        )
