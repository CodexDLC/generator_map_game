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
        ("editor.nodes.height.composition.masked_delta_node", "MaskedDeltaNode"),

        # Ландшафт.Маски
        ("editor.nodes.height.composition.slope_mask_node", "SlopeMaskNode"),

        # Ландшафт.Эрозия
        ("editor.nodes.height.erosion.landlab_erosion_node", "LandlabErosionNode"),

        # Универсальные.Шумы
        ("editor.nodes.universal.noises.perlin_noise_node", "PerlinNoiseNode"),
        ("editor.nodes.universal.noises.voronoi_noise_node", "VoronoiNoiseNode"),
        ("editor.nodes.universal.noises.multifractal_node", "MultiFractalNode"),

        # Универсальные.Математика
        ("editor.nodes.universal.math.normalize01_node", "Normalize01Node"),

        # Универсальные.Маски
        ("editor.nodes.universal.masks.mask_node", "MaskNode"),

        # Универсальные.Модули
        ("editor.nodes.universal.module.domain_warp_apply_node", "DomainWarpApplyNode"),
        ("editor.nodes.universal.module.warp_field_node", "WarpFieldNode"),

        # UI
        ("editor.nodes.backdrop_node", "CustomBackdropNode"),
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
