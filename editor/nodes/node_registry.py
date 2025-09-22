# ==============================================================================
# Файл: editor/nodes/node_registry.py
# Назначение: Централизованная регистрация всех нод в редакторе.
# ВЕРСИЯ 2.0: Добавлены новые ноды категорий Math и Effects.
# ==============================================================================

# --- Существующие ноды ---
from editor.nodes.generator.instructions.stamp_node import StampNode
from editor.nodes.generator.modules.border_mask_node import BorderMaskNode
from editor.nodes.generator.modules.mask_node import MaskNode
from editor.nodes.generator.modules.warp_node import WarpNode
from editor.nodes.generator.noises.noise_node import NoiseNode
from editor.nodes.generator.pipeline.blend_node import BlendNode
from editor.nodes.generator.pipeline.output_node import OutputNode
from editor.nodes.generator.pipeline.walker_node import WalkerNode
from editor.nodes.generator.pipeline.world_input_node import WorldInputNode

# --- НОВЫЕ НОДЫ (Импорт) ---

# Категория: Math
from editor.nodes.generator.math.math_node import (
    MathNode,
    ClampNode,
    NormalizeNode
)

# Категория: Effects
from editor.nodes.generator.effects.terracer_node import TerracerNode
from editor.nodes.generator.effects.selective_smooth_node import SelectiveSmoothNode
from editor.nodes.generator.effects.slope_limiter_node import SlopeLimiterNode
from editor.nodes.generator.effects.anti_ripple_node import AntiRippleNode


def register_all_nodes(graph):
    """
    Регистрирует все доступные ноды в переданном графе.
    """
    print("[NodeRegistry] Registering all nodes...")

    # --- Старые ноды ---
    graph.register_node(WorldInputNode)
    graph.register_node(NoiseNode)
    graph.register_node(WarpNode)
    graph.register_node(BlendNode)
    graph.register_node(MaskNode)
    graph.register_node(BorderMaskNode)
    graph.register_node(WalkerNode)
    graph.register_node(StampNode)
    graph.register_node(OutputNode)

    # --- НОВЫЕ НОДЫ (Регистрация) ---

    # Math
    graph.register_node(MathNode)
    graph.register_node(ClampNode)
    graph.register_node(NormalizeNode)

    # Effects
    graph.register_node(TerracerNode)
    graph.register_node(SelectiveSmoothNode)
    graph.register_node(SlopeLimiterNode)
    graph.register_node(AntiRippleNode)

    print("[NodeRegistry] All nodes registered successfully.")