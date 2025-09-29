# ==============================================================================
# Файл: editor/nodes/node_registry.py
# ВЕРСИЯ ДЛЯ ТЕСТИРОВАНИЯ (ИСПРАВЛЕННАЯ): Пути импорта соответствуют
#                                        новой структуре папок.
# ==============================================================================

from __future__ import annotations
import importlib
import logging
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

def _import_class(module_path: str, class_name: str) -> Optional[type]:
    """Вспомогательная функция для безопасного импорта класса."""
    try:
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name, None)
        if cls is None:
            logger.warning(f"Класс '{class_name}' не найден в модуле '{module_path}'")
        return cls
    except ImportError as e:
        logger.warning(f"Не удалось импортировать модуль {module_path}: {e}")
        return None

def _safe_register(graph: Any, node_cls: Any) -> bool:
    """Безопасно регистрирует класс ноды в графе."""
    if not node_cls:
        return False
    try:
        graph.register_node(node_cls)
        return True
    except Exception as e:
        logger.exception(f"Ошибка при регистрации ноды {getattr(node_cls, '__name__', node_cls)}: {e}")
        return False

def register_all_nodes(graph: Any) -> None:
    print("[NodeRegistry] Регистрация нод для теста...")
    if graph is None:
        print("[NodeRegistry] ОШИБКА: Граф не передан.")
        return

    # --- ЕДИНЫЙ СПИСОК ИМПОРТОВ (io + noises) ---
    # --- ЕДИНЫЙ СПИСОК ИМПОРТОВ (io + noises + math + masks + warp) ---
    NODES_TO_IMPORT = [
        # IO
        ("editor.nodes.height.io.world_input_node", "WorldInputNode"),
        ("editor.nodes.height.io.output_node", "OutputNode"),

        # Noises (все отдают packet [0..1])
        ("editor.nodes.universal.noises.fbm_noise_node", "FBMNoiseNode"),
        ("editor.nodes.universal.noises.voronoi_noise_node", "VoronoiNoiseNode"),
        ("editor.nodes.universal.noises.value_noise_node", "ValueNoiseNode"),
        ("editor.nodes.universal.noises.simplex_noise_node", "SimplexNoiseNode"),

        # Math
        ("editor.nodes.universal.math.to_meters_node", "ToMetersNode"),
        ("editor.nodes.universal.math.normalize01_node", "Normalize01Node"),
        ("editor.nodes.universal.math.math_ops_node", "MathOpsNode"),

        # Masks
        ("editor.nodes.universal.masks.mask_node", "MaskNode"),

        # Warp (внешний доменный варп + генератор поля варпа)
        ("editor.nodes.universal.module.domain_warp_apply_node", "DomainWarpApplyNode"),
        ("editor.nodes.universal.module.warp_field_node", "WarpFieldNode"),

        ("editor.nodes.backdrop_node", "CustomBackdropNode"),

    ]

    # Сборка словаря {ClassName: cls}
    nodes_to_register = {}
    for module_path, class_name in NODES_TO_IMPORT:
        cls = _import_class(module_path, class_name)
        nodes_to_register[class_name] = cls

    ok, fail = 0, 0
    for name, cls in nodes_to_register.items():
        if _safe_register(graph, cls):
            ok += 1
            print(f"[NodeRegistry]   OK  -> {name}")
        else:
            fail += 1
            print(f"[NodeRegistry]   ERR -> {name} (не найден или ошибка)")

    print(f"[NodeRegistry] Готово. Зарегистрировано: {ok}, Ошибок: {fail}.")
