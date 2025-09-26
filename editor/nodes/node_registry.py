# ==============================================================================
# Файл: editor/nodes/node_registry.py
# ВЕРСИЯ 4.0: Гибкие импорты (несколько кандидатов на каждый модуль),
#             понятные логи, безопасная регистрация, минимальный профиль.
#             Регистрируем: WorldInputNode, NoiseNode, OutputNode.
# ==============================================================================

from __future__ import annotations
import importlib
import logging
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

def _import_first(candidates: List[str], class_name: str) -> Optional[type]:
    """
    Пробует по очереди пути из candidates, импортирует модуль и достаёт класс class_name.
    Возвращает сам класс или None, если не удалось.
    """
    last_err: Optional[Exception] = None
    for mod in candidates:
        try:
            m = importlib.import_module(mod)
            cls = getattr(m, class_name, None)
            if cls is None:
                raise AttributeError(f"Модуль '{mod}' не содержит класс '{class_name}'")
            logger.info("Импортирован %s из %s", class_name, mod)
            print(f"[NodeRegistry] import OK: {class_name} <- {mod}")
            return cls
        except Exception as e:
            last_err = e
            logger.debug("Не удалось импортировать %s из %s: %s", class_name, mod, e)
    if last_err:
        logger.exception("Ошибка импорта %s (кандидаты: %s): %s", class_name, candidates, last_err)
        print(f"[NodeRegistry] import FAIL: {class_name}")
    return None


# --- Кандидаты путей для каждой ноды (перечень покрывает твои варианты структуры) ---

WORLD_INPUT_PATHS = [
    "editor.nodes.world_input_node",
    "editor.nodes.generator.pipeline.world_input_node",
    "editor.steps.world_input_node",
]

NOISE_NODE_PATHS = [
    "editor.nodes.noise_node",
    "editor.nodes.generator.noises.noise_node",
]

OUTPUT_NODE_PATHS = [
    "editor.nodes.output_node",
    "editor.nodes.generator.pipeline.output_node",
    "editor.steps.output_node",
]
MASKED_DELTA_PATHS = [
    "editor.nodes.masked_delta_node",
    "editor.nodes.composition.masked_delta_node",
]

HEIGHT_MERGE_PATHS = [
    "editor.nodes.height_merge_node",
    "editor.nodes.pipeline.height_merge_node",
]

SLOPE_MASK_NODE_PATHS = [
    "editor.nodes.slope_mask_node",
    "editor.nodes.masks.slope_mask_node",
]

def _resolve_active_nodes() -> List[Tuple[str, Any]]:
    WorldInputNode   = _import_first(WORLD_INPUT_PATHS, "WorldInputNode")
    NoiseNode        = _import_first(NOISE_NODE_PATHS, "NoiseNode")

    # новые ноды
    MaskedDeltaNode  = _import_first(MASKED_DELTA_PATHS, "MaskedDeltaNode")
    HeightMergeNode  = _import_first(HEIGHT_MERGE_PATHS, "HeightMergeNode")
    SlopeMaskNode    = _import_first(SLOPE_MASK_NODE_PATHS, "SlopeMaskNode")

    OutputNode       = _import_first(OUTPUT_NODE_PATHS, "OutputNode")

    return [
        ("WorldInputNode",  WorldInputNode),
        ("NoiseNode",       NoiseNode),
        ("MaskedDeltaNode", MaskedDeltaNode),
        ("HeightMergeNode", HeightMergeNode),
        ("SlopeMaskNode",   SlopeMaskNode),
        ("OutputNode",      OutputNode),
    ]

def _safe_register(graph: Any, node_cls: Any) -> bool:
    """
    Безопасно регистрирует класс ноды в графе.
    """
    if node_cls is None:
        return False

    if not hasattr(graph, "register_node") or not callable(getattr(graph, "register_node")):
        logger.error("Объект графа не поддерживает register_node(...): %r", graph)
        return False

    try:
        graph.register_node(node_cls)
        return True
    except Exception as e:
        logger.exception("Ошибка при регистрации ноды %s: %s",
                         getattr(node_cls, "__name__", node_cls), e)
        return False


def register_all_nodes(graph: Any) -> None:
    """
    Регистрирует минимальный набор нод. Печатает краткую сводку.
    """
    print("[NodeRegistry] Registering nodes (flex imports)…")
    if graph is None or not hasattr(graph, "register_node"):
        print("[NodeRegistry] ABORT: graph invalid")
        logger.error("Граф не передан или не поддерживает register_node(...)")
        return

    active_nodes = _resolve_active_nodes()

    ok, fail = 0, 0
    for display_name, node_cls in active_nodes:
        if _safe_register(graph, node_cls):
            ok += 1
            print(f"[NodeRegistry]   OK  -> {display_name}")
        else:
            fail += 1
            print(f"[NodeRegistry]   ERR -> {display_name}")

    print(f"[NodeRegistry] Done. Registered: {ok}, Failed: {fail}.")
    if fail:
        print("[NodeRegistry] Подсказка: проверь реальное расположение файлов и наличие __init__.py в пакетах.")
