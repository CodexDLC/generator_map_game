
from __future__ import annotations
import sys, pathlib, json
from typing import Dict, Any

# Добавляем корень (для engine.*)
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.worldgen_core.world.world_base import WorldBaseGenerator
from engine.worldgen_core.base.preset import Preset
from engine.worldgen_core.base.export import write_chunk_rle_json, write_chunk_meta_json

ARTIFACTS = ROOT / "artifacts" / "world"

def ensure_dir(p: pathlib.Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def load_preset(path: pathlib.Path) -> Preset:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Preset.from_dict(data)

def generate_or_load(seed: int, cx: int, cz: int, preset_path: pathlib.Path) -> Dict[str, Any]:
    """Возвращает dict с полями: header/layers/fields/ports/blocked/metrics/... (как в RLE JSON)."""
    out_dir = ARTIFACTS / str(seed) / f"{cx}_{cz}"
    rle_path = out_dir / "chunk.rle.json"
    meta_path = out_dir / "chunk.meta.json"

    if rle_path.exists() and meta_path.exists():
        with open(rle_path, "r", encoding="utf-8") as f:
            rle = json.load(f)
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        rle["_meta"] = meta  # вложим для удобства
        return rle

    # Иначе генерим
    preset = load_preset(preset_path)
    gen = WorldBaseGenerator(preset)
    res = gen.generate({"seed": seed, "cx": cx, "cz": cz})

    ensure_dir(out_dir)
    # client RLE
    write_chunk_rle_json(str(rle_path), res.header(), res.layers, res.fields, res.ports, res.blocked)
    # meta
    write_chunk_meta_json(str(meta_path), res.meta_header(), res.metrics, res.stage_seeds, res.capabilities)

    with open(rle_path, "r", encoding="utf-8") as f:
        rle = json.load(f)
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    rle["_meta"] = meta
    return rle
