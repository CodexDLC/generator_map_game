# editor/nodes/_helpers/cache_utils.py
from __future__ import annotations
from typing import Any, Tuple

import numpy as np


# --- ИЗМЕНЕНИЕ: Добавляем новую функцию ---
def make_properties_signature(node) -> Tuple[Any, ...]:
    """Создает сигнатуру на основе текущих свойств ноды."""
    try:
        # Используем _prop_meta, так как там описаны все свойства, влияющие на вычисления
        props = tuple(sorted(
            (name, node.get_property(name)) for name in node._prop_meta.keys()
        ))
        return props
    except Exception:
        # Возвращаем уникальный ID как запасной вариант, если что-то пошло не так
        return (id(node),)
# --- КОНЕЦ ИЗМЕНЕНИЯ ---


def make_context_signature(context: dict) -> Tuple[Any, ...]:
    """
    Создает уникальную сигнатуру для context.
    ИСПРАВЛЕНИЕ: Теперь включает краткую сводку по world_input_noise,
    чтобы кэш для WorldInputNode сбрасывался при смене региона.
    """
    try:
        grid_shape = context.get("x_coords", np.array([])).shape
        project_data = context.get("project", {}) or {}
        global_noise = project_data.get("global_noise", {}) or {}
        gn_sig = tuple(sorted(global_noise.items()))

        # --- ГЛАВНОЕ ИЗМЕНЕНИЕ ---
        # Добавляем в сигнатуру базовую статистику по входному шуму.
        # Это делает сигнатуру уникальной для каждого региона.
        noise_sig = None
        noise_arr = context.get("world_input_noise")
        if isinstance(noise_arr, np.ndarray) and noise_arr.size > 0:
            # Берем несколько ключевых значений, чтобы создать уникальный отпечаток
            noise_sig = (
                float(np.mean(noise_arr)),
                float(np.min(noise_arr)),
                float(np.max(noise_arr)),
                noise_arr.shape
            )
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

        return "v6", grid_shape, gn_sig, noise_sig

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
