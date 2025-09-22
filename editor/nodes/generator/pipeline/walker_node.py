# ==============================================================================
# Файл: editor/nodes/walker_node.py
# ВЕРСИЯ 2.1: Исправлена логика получения данных с входа.
# ==============================================================================
import numpy as np
from editor.nodes.base_node import GeneratorNode
from game_engine_restructured.algorithms.terrain.steps.blending import apply_walker_stampede


class WalkerNode(GeneratorNode):
    __identifier__ = 'generator.pipeline'
    NODE_NAME = 'Walker Agent'

    def __init__(self):
        super().__init__()

        # Основной конвейер
        self.add_input('Height In', 'In')
        # Входы для инструкций
        self.add_input('Stamp In', 'Stamp')
        # (В будущем добавим сюда Path Logic In, Placement In и т.д.)
        self.add_output('Height Out', 'Out')

        # Настройки самого агента (не штампа)
        self.add_combo_menu('blend_mode', 'Blend Mode', items=['add', 'subtract', 'multiply'])

        self.set_color(80, 50, 10)

    def compute(self, context):
        # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
        # Получаем карту высот с входа 'Height In'
        input_port = self.get_input(0)
        # Сначала проверяем, есть ли подключение
        if input_port and input_port.connected_ports():
            # Если есть, получаем исходную ноду и вычисляем ее результат
            source_node = input_port.connected_ports()[0].node()
            height_map = source_node.compute(context)
        else:
            # Если на вход ничего не подано, начинаем с пустой карты (земля на уровне 0)
            height_map = np.zeros_like(context["x_coords"])
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

        local_context = context.copy()
        local_context["main_heightmap"] = height_map

        # Получаем инструкцию для штампа
        stamp_port = self.get_input(1)
        if stamp_port and stamp_port.connected_ports():
            stamp_node = stamp_port.connected_ports()[0].node()
            stamp_params = stamp_node.compute(context)
        else:
            # Если штамп не подключен, агент ничего не будет делать
            print("  -> [WalkerNode] No stamp data connected. Skipping.")
            self._result_cache = height_map
            return self._result_cache

        # Собираем параметры для "мозга"
        # (Временно оставим логику и размещение здесь, пока не создали для них ноды)
        params = {
            "placement": {"mode": "corner", "corner": "north_west"},
            "stamp": stamp_params,  # <-- Используем данные от StampNode
            "walker": {"path_mode": "perimeter", "step_distance_ratio": 0.5, "perimeter_offset_tiles": 512.0},
            "blend_mode": self.get_property('blend_mode')
        }

        # Вызываем "мозг" агента
        print("  -> [WalkerNode] Executing walker agent with instructions...")
        result_context = apply_walker_stampede(params, local_context)
        final_map = result_context["main_heightmap"]

        self._result_cache = final_map
        return self._result_cache