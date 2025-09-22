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


def run_graph(graph, context: dict, on_tick=None):
    """
    graph: NodeGraphQt.NodeGraph
    context: dict с x_coords, z_coords, cell_size, seed, и т.п.
    on_tick: callable(percent:int, message:str) | None
    """
    _trace("run_graph: start")
    if on_tick: on_tick(5, "Поиск выхода…")
    out = _find_output_node(graph)
    _trace(f"run_graph: output node = {out}")

    if on_tick: on_tick(10, "Вычисление…")
    _trace("run_graph: calling out.compute(context)")
    result = out.compute(context)
    _trace(f"run_graph: out.compute returned type={type(result)}")

    if result is None:
        raise RuntimeError("Output.compute вернул None (проверь соединения)")
    if not isinstance(result, np.ndarray):
        raise RuntimeError(f"Ожидался np.ndarray, получено {type(result)}")
    if result.ndim != 2:
        raise RuntimeError(f"Ожидалась 2D карта высот, shape={result.shape}")
    if on_tick: on_tick(95, f"Размер: {result.shape}")

    # стандартизируем dtype
    return result.astype(np.float32, copy=False)
