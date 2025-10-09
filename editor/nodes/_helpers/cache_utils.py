# editor/nodes/_helpers/cache_utils.py
from __future__ import annotations
from typing import Any, Tuple

import numpy as np


def make_properties_signature(node) -> Tuple[Any, ...]:
    """Создает сигнатуру на основе текущих свойств ноды."""
    try:
        props = tuple(sorted(
            (name, node.get_property(name)) for name in node._prop_meta.keys()
        ))
        return props
    except Exception:
        return (id(node),)


def make_context_signature(context: dict) -> Tuple[Any, ...]:
    """
    Создает уникальную сигнатуру для context.
    ИСПРАВЛЕНИЕ: Теперь использует актуальные данные 'global_noise' из UI.
    """
    try:
        grid_shape = context.get("x_coords", np.array([])).shape

        # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
        # Мы больше не берем global_noise из project_data, так как в project_manager
        # мы уже подменили его на актуальные данные из UI.
        # Просто берем то, что лежит в context['project'].
        project_context = context.get("project", {}) or {}
        global_noise = project_context.get("global_noise", {}) or {}
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

        gn_sig = tuple(sorted(global_noise.items()))

        noise_sig = None
        noise_arr = context.get("world_input_noise")
        if isinstance(noise_arr, np.ndarray) and noise_arr.size > 0:
            noise_sig = (
                float(np.mean(noise_arr)),
                float(np.min(noise_arr)),
                float(np.max(noise_arr)),
                noise_arr.shape
            )

        return "v7", grid_shape, gn_sig, noise_sig

    except Exception:
        return "fallback", id(context)


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