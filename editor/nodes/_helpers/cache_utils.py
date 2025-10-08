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
    Создает уникальную и надежную сигнатуру для словаря context.
    Включает в себя ключевые параметры, влияющие на генерацию,
    такие как разрешение сетки и настройки глобального шума.
    """
    try:
        # 1. Получаем разрешение сетки из координат. Это самый важный параметр.
        grid_shape = context.get("x_coords", np.array([])).shape

        # 2. Безопасно получаем вложенные словари с настройками.
        project_data = context.get("project", {}) or {}
        global_noise = project_data.get("global_noise", {}) or {}

        # 3. Создаем отпечаток всех настроек глобального шума.
        # Сортируем по ключу, чтобы порядок был всегда одинаковый.
        gn_sig = tuple(sorted(global_noise.items()))

        # 4. Собираем финальную сигнатуру. "v5" - это номер версии нашей логики,
        # чтобы при будущих изменениях все старые кэши автоматически стали невалидными.
        return "v5", grid_shape, gn_sig

    except Exception:
        # Если при создании сигнатуры что-то пошло не так,
        # возвращаем гарантированно уникальное значение, чтобы избежать
        # ошибочного использования кэша.
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
