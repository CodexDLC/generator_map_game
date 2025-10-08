# editor/graph_runner.py
import logging
import numpy as np

from editor.utils.diag import diag_array
from game_engine_restructured.numerics.field_packet import get_data, is_packet

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
        tick(10, f"Вычисление от ноды '{out_node.name()}'…")
        result = out_node.compute(context)
        logger.info("Graph computation finished successfully.")

    except Exception:
        logger.exception("An exception occurred during graph execution.")
        raise

    # --- Валидация и стандартизация результата ---
    logger.info("Validating final result...")

    diag_array(result, name="final_map (before validate)")

    # Проверяем, является ли результат field_packet
    if is_packet(result):
        arr = get_data(result)  # Извлекаем np.ndarray из field_packet
    else:
        arr = np.asarray(result)

    # Проверка на None
    if arr is None:
        logger.error("Validation failed: Output node returned None or empty data.")
        raise RuntimeError("Output.compute вернул None или пустые данные (проверь соединения)")

    # Проверка на форму
    if arr.ndim != 2:
        logger.error(f"Validation failed: Expected 2D heightmap, but got shape {getattr(arr, 'shape', 'N/A')}")
        raise RuntimeError(f"Ожидалась 2D карта высот, shape={getattr(arr, 'shape', None)}")

    # Проверка на корректность значений
    if not np.isfinite(arr).all():
        logger.error("Validation failed: Result contains NaN or Inf values.")
        raise RuntimeError("Результат содержит NaN/Inf")

    # Приводим к float32
    arr = arr.astype(np.float32, copy=False, order="C")

    # Дополнительная проверка формы на совпадение с context["x_coords"]
    if "x_coords" in context and isinstance(context["x_coords"], np.ndarray):
        if arr.shape != context["x_coords"].shape:
            logger.warning(f"Shape mismatch: result shape={arr.shape}, x_coords shape={context['x_coords'].shape}. Using zeros.")
            arr = np.zeros_like(context["x_coords"], dtype=np.float32)

    logger.info(f"Validation successful. Final map shape: {arr.shape}")
    tick(95, f"Размер: {arr.shape}")
    return arr