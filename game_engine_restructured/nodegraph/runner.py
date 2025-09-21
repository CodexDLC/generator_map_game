# runner.py
import json
from .base import Context, REGISTRY

def run_graph(preset_json: dict, ctx: Context) -> dict:
    buffers: dict[str, dict] = {}  # id -> outputs
    for node_def in preset_json["nodes"]:
        t = node_def["type"]
        nid = node_def["id"]
        params = node_def.get("params", {})
        inputs = {k: resolve_path(v, buffers) for k, v in node_def.get("inputs", {}).items()}
        node = REGISTRY[t](params)
        outputs = node.apply(ctx, inputs)
        buffers[nid] = outputs
    out_ref = preset_json["outputs"]
    return {k: resolve_path(v, buffers) for k, v in out_ref.items()}

def resolve_path(ref: str, buffers: dict):
    # "@node.output" или литерал
    if isinstance(ref, str) and ref.startswith("@"):
        nid, key = ref[1:].split(".")
        return buffers[nid][key]
    return ref
