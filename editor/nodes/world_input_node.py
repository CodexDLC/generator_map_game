# ==============================================================================
# Файл: editor/nodes/world_input_node.py
# Назначение: Стартовая нода, которая генерирует базовый ландшафт мира.
# ==============================================================================

from .base_node import GeneratorNode
# Импортируем нашу функцию для генерации шума
from game_engine_restructured.algorithms.terrain.nodes.noise import _generate_noise_field


class WorldInputNode(GeneratorNode):
    # Уникальный идентификатор для библиотеки нодов
    __identifier__ = 'generator.nodes'
    # Имя, которое будет отображаться в палитре и на самом ноде
    NODE_NAME = 'World Input'

    def __init__(self):
        super().__init__()

        # У этой ноды нет входов, только выход для карты высот
        self.add_output('height')

        # Добавляем настраиваемые параметры прямо в ноду
        self.add_text_input('scale_tiles', 'Scale (tiles)', tab='Continental Noise', text='6000')
        self.add_text_input('octaves', 'Octaves', tab='Continental Noise', text='3')
        self.add_text_input('amp_m', 'Amplitude (m)', tab='Continental Noise', text='400')
        self.add_checkbox('ridge', 'Ridge', tab='Continental Noise', state=False)

        # Задаем цвет, чтобы она визуально отличалась
        self.set_color(80, 25, 30)

    def compute(self, context):
        """
        Главный метод вычисления. Он игнорирует входящие данные (т.к. их нет)
        и генерирует "сырой" ландшафт на основе глобальных настроек из context
        и своих собственных параметров.
        """

        # --- ШАГ 1: Получаем параметры самой ноды ---
        def _f(name, default):
            v = self.get_property(name)
            return float(v) if v else default

        def _i(name, default):
            v = self.get_property(name)
            return int(v) if v else default

        scale_tiles = _f('scale_tiles', 6000.0)
        octaves = _i('octaves', 3)
        amp_m = _f('amp_m', 400.0)
        ridge = bool(self.get_property('ridge'))

        # Собираем параметры для функции генерации шума
        noise_params = {
            "scale_tiles": scale_tiles,
            "octaves": octaves,
            "ridge": ridge,
            "amp_m": amp_m,
            "seed_offset": 0,  # У базового шума нет смещения сида
            "blend_mode": "replace"  # Он всегда заменяет, а не добавляет
        }

        # --- ШАГ 2: Вызываем генератор шума с правильным контекстом ---
        # Функция _generate_noise_field уже умеет работать с глобальными координатами,
        # если мы их передадим в `context`. Мы сделаем это на следующем этапе.
        print(
            f"  -> [WorldInput] Generating base continent at offset ({context.get('global_x_offset', 0)}, {context.get('global_z_offset', 0)})...")
        height_map = _generate_noise_field(noise_params, context)

        self._result_cache = height_map
        return self._result_cache