# ==============================================================================
# Файл: editor/nodes/border_mask_node.py
# Назначение: Нода для создания маски, обеспечивающей бесшовные края региона.
# ==============================================================================
from editor.nodes.base_node import GeneratorNode
# Импортируем нашу функцию из движка
from game_engine_restructured.algorithms.terrain.uber_blend import donut_mask


class BorderMaskNode(GeneratorNode):
    __identifier__ = 'Ландшафт.Модули'
    NODE_NAME = 'Border Mask'

    def __init__(self):
        super().__init__()

        # У этой ноды нет входов, она работает с глобальными координатами
        self.add_output('Mask', 'Out')

        # Добавляем настраиваемые параметры
        self.add_text_input('blend_width', 'Blend Width (m)', tab='Mask Settings', text='50.0')
        self.add_text_input('inner_pad', 'Inner Padding (m)', tab='Mask Settings', text='0.0')
        self.add_combo_menu('falloff', 'Falloff Type', items=['smoothstep', 'linear', 'cosine'], tab='Mask Settings')

        self.set_color(90, 90, 30)

    def compute(self, context):
        print("  -> [BorderMaskNode] Creating seamless border mask...")

        def _f(name, default):
            v = self.get_property(name)
            try:
                return float(v)
            except (ValueError, TypeError):
                return default

        blend_width_m = _f('blend_width', 50.0)
        inner_pad_m = _f('inner_pad', 0.0)
        falloff = self.get_property('falloff')

        # --- Вычисляем границы текущего региона ---
        # Это ключевой момент: нода знает, где она находится в мире
        size_px = context['x_coords'].shape[0]
        cell_size = context['cell_size']
        size_m = size_px * cell_size

        # Получаем глобальные координаты из контекста
        x_coords = context['x_coords']
        z_coords = context['z_coords']

        # Определяем границы региона, в котором мы находимся
        min_x = x_coords[0, 0]
        max_x = x_coords[0, -1]
        min_z = z_coords[0, 0]
        max_z = z_coords[-1, 0]
        bounds = (min_x, max_x, min_z, max_z)

        # --- Вызываем "мозг" для создания маски ---
        mask = donut_mask(
            world_x=x_coords,
            world_z=z_coords,
            region_bounds=bounds,
            blend_width_m=blend_width_m,
            inner_pad_m=inner_pad_m,
            falloff=falloff
        )

        self._result_cache = mask
        return self._result_cache