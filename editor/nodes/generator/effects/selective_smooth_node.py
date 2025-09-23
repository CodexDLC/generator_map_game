# ==============================================================================
# Файл: editor/nodes/generator/effects/selective_smooth_node.py
# Назначение: Нода для выборочного сглаживания пологих участков.
# ==============================================================================
from editor.nodes.base_node import GeneratorNode
# Импортируем "мозг" из нашего движка
from game_engine_restructured.algorithms.terrain.steps.effects import apply_selective_smoothing


class SelectiveSmoothNode(GeneratorNode):
    # Указываем ту же категорию, что и у Terracer
    __identifier__ = 'Ландшафт.Эффекты'
    NODE_NAME = 'Selective Smooth'

    def __init__(self):
        super().__init__()

        # --- Входы и выходы ---
        self.add_input('In')
        self.add_output('Out')

        # --- Настройки ---
        self.add_text_input('angle_deg', 'Slope Angle (°)', '35.0', tab='Settings')
        self.add_text_input('detail_keep', 'Detail Keep (0-1)', '0.35', tab='Settings')
        self.add_text_input('blur_iters', 'Blur Iterations', '1', tab='Settings')

        self.set_color(90, 65, 30)  # Другой оттенок оранжевого

    def compute(self, context):
        port_in = self.get_input(0)
        if not (port_in and port_in.connected_ports()):
            return context["main_heightmap"]

        local_context = context.copy()
        local_context["main_heightmap"] = port_in.connected_ports()[0].node().compute(context)

        def _f(name, default):
            v = self.get_property(name)
            try:
                return float(v)
            except (ValueError, TypeError):
                return default

        def _i(name, default):
            v = self.get_property(name)
            try:
                return int(v)
            except (ValueError, TypeError):
                return default

        # Собираем параметры для функции-обработчика
        params = {
            "angle_deg": _f('angle_deg', 35.0),
            "detail_keep": _f('detail_keep', 0.35),
            "blur_iters": _i('blur_iters', 1)
        }

        # Вызываем "мозг" из движка
        result_context = apply_selective_smoothing(params, local_context)

        # Возвращаем измененную карту высот
        result_map = result_context["main_heightmap"]
        self._result_cache = result_map
        return self._result_cache