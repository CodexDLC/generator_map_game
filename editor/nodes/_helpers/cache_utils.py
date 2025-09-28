# editor/nodes/_helpers/cache_utils.py
from __future__ import annotations
from typing import Any, Tuple

def make_context_signature(context: dict) -> Tuple[Any, ...]:
    try:
        seed = int(context.get("seed"))
        cell_size = float(context.get("cell_size"))
        x = context.get("x_coords")
        grid_shape = getattr(x, "shape", None)
        gn = context.get("global_noise")
        gn_sig = tuple(sorted(gn.items())) if isinstance(gn, dict) else None
        ctx_rev = context.get("_ctx_rev", None)
        return ("v2", seed, cell_size, grid_shape, gn_sig, ctx_rev)
    except Exception:
        return ("v2_fallback", id(context))

def make_upstream_signature(node) -> Tuple[Any, ...]:
    sig = []
    for p in node.inputs().values():
        conns = p.connected_ports()
        if not conns:
            sig.append((p.name(), None))
        else:
            ids = tuple(sorted((c.node().id, getattr(c.node(), "_rev", 0)) for c in conns))
            sig.append((p.name(), ids))
    return tuple(sig)
