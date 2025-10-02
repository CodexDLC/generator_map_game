# editor/nodes/node_registry.py
from __future__ import annotations
import importlib
import logging

logger = logging.getLogger(__name__)


def register_all_nodes(graph):
    if graph is None:
        logger.critical("[NodeRegistry] Graph object is None.")
        return

    NODES_TO_IMPORT = [
        # Ландшафт.Пайплайн
        ("editor.nodes.height.io.world_input_node", "WorldInputNode"),
        ("editor.nodes.height.io.output_node", "OutputNode"),

        # Ландшафт.Композиция
        ("editor.nodes.height.composition.combiner_node", "CombinerNode"),

        # Ландшафт.Эрозия
        ("editor.nodes.height.erosion.landlab_erosion_node", "LandlabErosionNode"),
        ("editor.nodes.height.erosion.easy_erosion_node", "EasyErosionNode"),

        # Универсальные.Шумы
        ("editor.nodes.universal.noises.perlin_noise_node", "PerlinNoiseNode"),
        ("editor.nodes.universal.noises.voronoi_noise_node", "VoronoiNoiseNode"),
        ("editor.nodes.universal.noises.multifractal_node", "MultiFractalNode"),

        # Универсальные.Математика
        ("editor.nodes.universal.math.normalize01_node", "Normalize01Node"),

        # UI
        ("editor.nodes.backdrop_node", "CustomBackdropNode"),
        ("editor.nodes.universal.debug.sphere_projection_node", "SphereProjectionNode"),
    ]

    ok, fail = 0, 0
    for module_path, class_name in NODES_TO_IMPORT:
        try:
            module = importlib.import_module(module_path)
            node_class = getattr(module, class_name)
            graph.register_node(node_class)
            ok += 1
        except Exception as e:
            logger.error(f"Failed to register node '{class_name}' from '{module_path}': {e}")
            fail += 1

    logger.info(f"Node registration complete. Succeeded: {ok}, Failed: {fail}.")
