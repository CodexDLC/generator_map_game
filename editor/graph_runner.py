# editor/graph_runner.py
import logging
import numpy as np

logger = logging.getLogger(__name__)


def run_graph(out_node, context, on_tick=lambda p, m: True):
    """
    Запускает вычисление графа, начиная с переданной выходной ноды.

    Args:
        out_node: Нода (например, OutputNode), с которой начинается вычисление.
        context: Словарь с параметрами для генерации.
        on_tick: Callback для отслеживания прогресса.
    """

    def tick(p, m):
        try:
            if on_tick:
                return on_tick(int(p), str(m))
        except Exception:
            logger.warning("Error in on_tick callback.", exc_info=True)
            return None

    try:
        logger.info("Graph run started.")
        # ИЗМЕНЕНИЕ: Мы больше не ищем выходную ноду здесь.
        # Она уже найдена и передана как аргумент `out_node`.
        # tick(5, "Поиск выхода…")
        # out_node = _find_output_node(graph) # <--- УБИРАЕМ ЭТУ ЛОГИКУ

        tick(10, f"Вычисление от ноды '{out_node.name()}'…")
        result = out_node.compute(context)
        logger.info("Graph computation finished successfully.")

    except Exception:
        logger.exception("An exception occurred during graph execution.")
        raise

    # --- Валидация и стандартизация результата ---
    logger.info("Validating final result...")
    if result is None:
        # Эта проверка остается на случай, если сама нода вернет None
        logger.error("Validation failed: Output node returned None.")
        raise RuntimeError("Output.compute вернул None (проверь соединения)")

    arr = np.asarray(result)

    if arr.ndim != 2:
        logger.error(f"Validation failed: Expected 2D heightmap, but got shape {getattr(arr, 'shape', 'N/A')}")
        raise RuntimeError(f"Ожидалась 2D карта высот, shape={getattr(arr, 'shape', None)}")

    if not np.isfinite(arr).all():
        logger.error("Validation failed: Result contains NaN or Inf values.")
        raise RuntimeError("Результат содержит NaN/Inf")

    arr = arr.astype(np.float32, copy=False, order="C")

    logger.info(f"Validation successful. Final map shape: {arr.shape}")
    tick(95, f"Размер: {arr.shape}")
    return arr