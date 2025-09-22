# ==============================================================================
# Файл: editor/graph_runner.py
# Назначение: Унифицированный запуск графа нод. Никаких Qt/VisPy/движка.
# ==============================================================================

from __future__ import annotations

import numpy as np
import sys
def _trace(msg):
    print(f"[TRACE/RUNNER] {msg}", flush=True, file=sys.stdout)


def _find_output_node(graph):
    _trace("find_output: listing nodes")
    nodes = list(graph.all_nodes())  # исключения ловятся выше
    outs = [n for n in nodes if getattr(n, "NODE_NAME", "") == "Output"]
    _trace(f"find_output: found {len(outs)} output(s)")
    if not outs:
        raise RuntimeError("В графе нет нода 'Output'")
    return outs[0]


def run_graph(graph, context, on_tick=lambda p, m: True):
    """
    graph: NodeGraphQt.NodeGraph
    context: dict с x_coords, z_coords, cell_size, seed, ...
    on_tick: callable(percent:int, message:str) | None
    """
    import numpy as np
    import traceback, sys

    def tick(p, m):
        try:
            return on_tick and on_tick(int(p), str(m))
        except Exception:
            return None

    try:
        _trace("run_graph: start")
        tick(5, "Поиск выхода…")
        out = _find_output_node(graph)
        _trace(f"run_graph: output node = {out!r}")

        tick(10, "Вычисление…")
        _trace("run_graph: calling out.compute(context)")
        result = out.compute(context)          # все исключения ловим ниже
        _trace(f"run_graph: out.compute returned type={type(result)}")

    except Exception as e:
        tb = traceback.format_exc()
        msg = f"{e}\n--- TRACEBACK ---\n{tb}"
        print(f"[TRACE/RUNNER/EXC] {msg}", flush=True, file=sys.stdout)
        # пробрасываем РАЗВЁРНУТУЮ ошибку в воркер/диалог
        raise RuntimeError(msg)

    # --- Валидация и стандартизация результата ---
    if result is None:
        raise RuntimeError("Output.compute вернул None (проверь соединения)")
    arr = np.asarray(result)

    if arr.ndim != 2:
        raise RuntimeError(f"Ожидалась 2D карта высот, shape={getattr(arr, 'shape', None)}")
    if not np.isfinite(arr).all():
        raise RuntimeError("Результат содержит NaN/Inf")

    # приведение типов для VisPy/GL
    arr = arr.astype(np.float32, copy=False, order="C")

    tick(95, f"Размер: {arr.shape}")
    return arr
