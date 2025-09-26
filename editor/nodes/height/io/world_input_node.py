# ==============================================================================
# Файл: editor/nodes/height/io/world_input_node.py
# ВЕРСИЯ 4.7: Источник мирового шума -> всегда нормаль [0..1] в field_packet.
# ==============================================================================

import logging
import numpy as np
from editor.nodes.base_node import GeneratorNode
from game_engine_restructured.algorithms.terrain.steps.noise import _generate_noise_field
from game_engine_restructured.numerics.field_packet import make_packet, SPACE_NORM
from game_engine_restructured.numerics.normalization import normalize01

logger = logging.getLogger(__name__)

IDENTIFIER_LBL = "Ландшафт.Пайплайн"
NODE_NAME_LBL  = "World Input"

DESCRIPTION_TEXT = """
Источник «сырого» мирового шума. Читает context['global_noise'] (scale_tiles, octaves, gain, lacunarity, seed_offset).
Возвращает field_packet с нормализованным шумом в диапазоне [0..1]. Метры здесь не применяются.
"""

class WorldInputNode(GeneratorNode):
    __identifier__ = IDENTIFIER_LBL
    NODE_NAME = NODE_NAME_LBL

    def __init__(self):
        super().__init__()
        self.add_output("height")
        self.set_color(80, 25, 30)
        self.set_description(DESCRIPTION_TEXT)

    def _compute(self, context):
        node_id = self.get_property("node_id")
        logger.info(f"Computing WorldInputNode (ID: {node_id})...")

        # Проверка формы контекста
        xc = context.get("x_coords")
        if not isinstance(xc, np.ndarray) or xc.ndim != 2:
            logger.critical("WorldInputNode: context['x_coords'] отсутствует/некорректен. Нули.")
            zeros = np.zeros((256, 256), dtype=np.float32)
            pkt = make_packet(zeros, space=SPACE_NORM, ref_m=1.0)
            self._result_cache = pkt
            return pkt

        noise_params = context.get("global_noise")
        if not isinstance(noise_params, dict):
            logger.critical("WorldInputNode: нет context['global_noise']. Нули.")
            zeros = np.zeros_like(context["x_coords"], dtype=np.float32)
            pkt = make_packet(zeros, space=SPACE_NORM, ref_m=1.0)
            self._result_cache = pkt
            return pkt

        # Параметры генератора; амплитуды/метры здесь не применяем
        params = dict(noise_params)
        params["seed_offset"] = int(params.get("seed_offset", 0))
        params["blend_mode"]  = "replace"  # для старых путей, не влияет на форму

        h = _generate_noise_field(params, context)  # ожидаем ndarray, близкий к [0..1]
        if not isinstance(h, np.ndarray) or h.ndim != 2 or h.shape != context["x_coords"].shape:
            logger.error("WorldInputNode: _generate_noise_field вернул некорректные данные. Нули.")
            h = np.zeros_like(context["x_coords"], dtype=np.float32)

        # Гарантия нормали [0..1] (без растяжек и округления)
        h = np.asarray(h, dtype=np.float32, copy=False)
        h01 = normalize01(h, mode="symmetric", clip_after=True, decimals=0, nan_fill=0.0)
        # и дальше в пакет кладём h01
        pkt = make_packet(h01, space=SPACE_NORM, ref_m=1.0)
        self._result_cache = pkt
        return pkt
