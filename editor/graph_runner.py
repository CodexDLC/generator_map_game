# ==============================================================================
# Файл: editor/graph_runner.py
# ВЕРСИЯ 2.0: Контекст вычислений вынесен наружу.
# ==============================================================================
import numpy as np


# ИСПРАВЛЕНИЕ (п.4): Убираем жестко заданный контекст.
def compute_graph(graph, context):
    """
    Находит выходной нод и запускает на нем вычисление, используя переданный контекст.
    """
    output_nodes = [n for n in graph.all_nodes() if n.NODE_NAME == 'Output']

    if not output_nodes:
        return None, "В графе отсутствует нод 'Output'!"

    if len(output_nodes) > 1:
        print("!!! ВНИМАНИЕ: В графе несколько нодов 'Output'. Используется первый найденный.")

    output_node = output_nodes[0]

    try:
        # Используем переданный 'context'
        final_result = output_node.compute(context)
        if final_result is not None:
            return final_result, f"Успешно. Размер карты: {final_result.shape}"
        else:
            return None, "Вычисление не дало результата (проверьте соединения)."
    except Exception as e:
        import traceback
        print(f"!!! КРИТИЧЕСКАЯ ОШИБКА при вычислении графа: {e}")
        traceback.print_exc()
        return None, f"Ошибка: {e}"