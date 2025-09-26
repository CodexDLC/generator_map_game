# ==============================================================================
# Файл: editor/nodes/generator/effects/terracer_node.py
# Назначение: Нода для создания процедурных террас на ландшафте.
# ==============================================================================
from editor.nodes.base_node import GeneratorNode
# Импортируем "мозг" из нашего движка
from game_engine_restructured.algorithms.terrain.steps.effects import apply_terracing


class TerracerNode(GeneratorNode):
    # Указываем новую категорию
    __identifier__ = 'Ландшафт.Эффекты'
    NODE_NAME = 'Terracer'

    def __init__(self):
        super().__init__()

        # --- Входы и выходы ---
        self.add_input('In')
        self.add_output('Out')

        # --- Настройки ---
        # Мы выносим все параметры из функции apply_terracing в удобные поля
        self.add_text_input('step_height_m', 'Step Height (m)', '60.0', tab='Terrace Shape')
        self.add_text_input('ledge_ratio', 'Ledge Ratio (0-1)', '0.7', tab='Terrace Shape')
        self.add_text_input('strength_m', 'Strength (m)', '10.0', tab='Terrace Shape')

        self.add_text_input('warp_strength', 'Warp Strength', '25.0', tab='Randomization')
        self.add_text_input('curvature_fade', 'Curvature Fade', '0.5', tab='Randomization')

        self.set_color(90, 50, 30)  # Оранжевый цвет для эффектов

    def compute(self, context):
        port_in = self.get_input(0)
        if not (port_in and port_in.connected_ports()):
            # Если на вход ничего не подано, ничего не делаем
            return context["main_heightmap"]

            # Создаем локальный контекст, чтобы не испортить глобальный
        local_context = context.copy()
        # В качестве основной карты высот берем данные с нашего входа
        local_context["main_heightmap"] = port_in.connected_ports()[0].node().compute(context)

        # Вспомогательная функция, чтобы безопасно читать числа из полей
        def _f(name, default):
            v = self.get_property(name)
            try:
                return float(v)
            except (ValueError, TypeError):
                return default

        # Собираем параметры для функции-обработчика в движке
        params = {
            "step_height_m": _f('step_height_m', 60.0),
            "ledge_ratio": _f('ledge_ratio', 0.7),
            "strength_m": _f('strength_m', 10.0),
            "randomization": {
                "warp_strength": _f('warp_strength', 25.0),
                "curvature_fade": _f('curvature_fade', 0.5)
            }
        }

        # Вызываем "мозг" из движка
        result_context = apply_terracing(params, local_context)

        # Возвращаем измененную карту высот
        result_map = result_context["main_heightmap"]
        self._result_cache = result_map
        return self._result_cache