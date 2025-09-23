# ==============================================================================
# Файл: editor/graph_runner.py
# Назначение: Унифицированный запуск графа нод. Никаких Qt/VisPy/движка.
# + ВНЕДРЕНИЕ ЛОГИРОВАНИЯ
# ==============================================================================
import logging  # <--- ДОБАВЛЕНО
import numpy as np
import sys
import traceback  # <--- ДОБАВЛЕНО

logger = logging.getLogger(__name__)  # <--- ДОБАВЛЕНО


def _find_output_node(graph):
    logger.debug("Searching for 'Output' node...")
    nodes = list(graph.all_nodes())
    outs = [n for n in nodes if getattr(n, "NODE_NAME", "") == "Output"]
    logger.debug(f"Found {len(outs)} output node(s).")
    if not outs:
        # Это критическая ошибка, поэтому уровень ERROR
        logger.error("No 'Output' node found in the graph!")
        raise RuntimeError("В графе нет нода 'Output'")
    return outs[0]


def run_graph(graph, context, on_tick=lambda p, m: True):
    """
    graph: NodeGraphQt.NodeGraph
    context: dict с x_coords, z_coords, cell_size, seed, ...
    on_tick: callable(percent:int, message:str) | None
    """

    def tick(p, m):
        try:
            return on_tick and on_tick(int(p), str(m))
        except Exception:
            # Не даем ошибке в колбэке прогресса уронить всю генерацию
            logger.warning("Error in on_tick callback.", exc_info=True)
            return None

    try:
        logger.info("Graph run started.")
        tick(5, "Поиск выхода…")
        out_node = _find_output_node(graph)

        tick(10, f"Вычисление от ноды '{out_node.name()}'…")
        result = out_node.compute(context)
        logger.info("Graph computation finished successfully.")

    except Exception:
        # logger.exception сам добавит полный трейсбек в лог
        logger.exception("An exception occurred during graph execution.")
        # Пробрасываем ошибку дальше, чтобы ее увидел воркер и UI
        raise

    # --- Валидация и стандартизация результата ---
    logger.info("Validating final result...")
    if result is None:
        logger.error("Validation failed: Output node returned None.")
        raise RuntimeError("Output.compute вернул None (проверь соединения)")

    arr = np.asarray(result)

    if arr.ndim != 2:
        logger.error(f"Validation failed: Expected 2D heightmap, but got shape {getattr(arr, 'shape', 'N/A')}")
        raise RuntimeError(f"Ожидалась 2D карта высот, shape={getattr(arr, 'shape', None)}")

    if not np.isfinite(arr).all():
        logger.error("Validation failed: Result contains NaN or Inf values.")
        raise RuntimeError("Результат содержит NaN/Inf")

    # приведение типов для VisPy/GL
    arr = arr.astype(np.float32, copy=False, order="C")

    logger.info(f"Validation successful. Final map shape: {arr.shape}")
    tick(95, f"Размер: {arr.shape}")
    return arr