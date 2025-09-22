# editor/nodes/node_registry.py
from editor.nodes.generator.instructions.stamp_node import StampNode
from editor.nodes.generator.modules.border_mask_node import BorderMaskNode
from editor.nodes.generator.modules.mask_node import MaskNode
from editor.nodes.generator.modules.warp_node import WarpNode
from editor.nodes.generator.noises.noise_node import NoiseNode
from editor.nodes.generator.pipeline.blend_node import BlendNode
from editor.nodes.generator.pipeline.output_node import OutputNode
from editor.nodes.generator.pipeline.walker_node import WalkerNode
from editor.nodes.generator.pipeline.world_input_node import WorldInputNode


def register_all_nodes(graph):
    """
    Регистрирует все доступные ноды в переданном графе.
    """
    print("[NodeRegistry] Registering all nodes...")

    # Просто добавляйте сюда новые ноды по мере их создания
    graph.register_node(WorldInputNode)
    graph.register_node(NoiseNode)
    graph.register_node(WarpNode)
    graph.register_node(BlendNode)
    graph.register_node(MaskNode)
    graph.register_node(BorderMaskNode)
    graph.register_node(WalkerNode)
    graph.register_node(StampNode)
    graph.register_node(OutputNode)

    print("[NodeRegistry] All nodes registered.")