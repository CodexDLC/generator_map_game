# ==============================================================================
# Файл: editor/nodes/world_input_node.py
# ВЕРСИЯ 4.1: Добавлено подробное описание ноды через set_description().
#             Нода — чистый источник «сырого» ландшафта из глобальных параметров.
# ==============================================================================
import logging
import numpy as np
from editor.nodes.base_node import GeneratorNode
from game_engine_restructured.algorithms.terrain.steps.noise import _generate_noise_field

logger = logging.getLogger(__name__)

class WorldInputNode(GeneratorNode):
    """
    Категория (palette): Ландшафт.Пайплайн
    Роль: Источник данных (Source)
    Выход: height — 2D np.ndarray (карта высот в метрах)
    Зависимости: читает параметры из context["global_noise"]
    """

    __identifier__ = 'Ландшафт.Пайплайн'
    NODE_NAME = 'World Input'

    def __init__(self):
        super().__init__()

        # Видимые порты
        self.add_output('height')

        # Цвет в палитре (бордовый оттенок)
        self.set_color(80, 25, 30)

        # Описание для панели свойств
        self.set_description("""
        Источник «сырого» ландшафта. Нода не требует входов и генерирует
        карту высот, читая глобальные параметры шума из контекста:

          context["global_noise"] : dict
            Обязательные ключи (пример):
              - scale_tiles : float   (масштаб шума в тайлах)
              - octaves     : int     (число октав)
              - amp_m       : float   (амплитуда в метрах)
              - ridge       : bool    (режим «гребней»)
            Допустимо расширение набора параметров алгоритмом.

        Выход:
          - height : np.ndarray (H×W, float32/float64) — карта высот (в метрах).

        Поведение:
          - Если global_noise отсутствует/некорректен, возвращается нулевая карта.
          - seed_offset и blend_mode принудительно задаются как служебные поля:
              seed_offset = 0, blend_mode = "replace"
        """)

    def compute(self, context):
        """
        Генерирует «сырой» ландшафт, используя глобальные параметры из контекста.
        """
        node_id = self.get_property('node_id')
        logger.info(f"Computing WorldInputNode (ID: {node_id})...")

        noise_params = context.get("global_noise")
        if not isinstance(noise_params, dict):
            logger.critical(f"Node {node_id}: 'global_noise' parameters not found in context! Returning zeros.")
            height_map = np.zeros_like(context["x_coords"], dtype=float)
            self._result_cache = height_map
            return self._result_cache

        logger.debug(f"  - Using global_noise params: {noise_params}")

        # Добавляем служебные параметры (не переопределяем входной словарь)
        params_for_generation = noise_params.copy()
        params_for_generation["seed_offset"] = 0
        params_for_generation["blend_mode"] = "replace"

        # Вызов генератора с глобальными параметрами и исходным контекстом
        height_map = _generate_noise_field(params_for_generation, context)

        # Мониторинг данных (Sanity Check)
        if height_map is not None:
            logger.debug(
                "  - Output map stats: shape=%s, min=%.3f, max=%.3f, has_nan=%s",
                getattr(height_map, "shape", None),
                float(np.nanmin(height_map)),
                float(np.nanmax(height_map)),
                bool(np.isnan(height_map).any()),
            )
        else:
            # Эта ситуация не должна происходить, но логируем на всякий случай
            logger.error("  - _generate_noise_field returned None!")
            height_map = np.zeros_like(context["x_coords"], dtype=float)

        self._result_cache = height_map
        return self._result_cache
