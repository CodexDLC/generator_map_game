# ==============================================================================
# Файл: editor/nodes/noise_node.py (Версия 2.1 - Исправлена ошибка)
# ==============================================================================
import numpy as np
from editor.nodes.base_node import GeneratorNode
from game_engine_restructured.algorithms.terrain.steps.noise import _generate_noise_field

class NoiseNode(GeneratorNode):
    __identifier__ = 'generator.noises'
    NODE_NAME = 'Noise'

    def __init__(self):
        super().__init__()

        # Входы
        self.add_input('height_in', 'Height In')
        self.add_input('warp_field', 'Warp Field (optional)')
        # Выход
        self.add_output('height_out')

        # Параметры самой ноды
        self.add_text_input('seed_offset', 'Seed Offset', tab='Noise', text='0')
        self.add_text_input('scale_tiles', 'Scale (tiles)', tab='Noise', text='1500')
        self.add_text_input('octaves', 'Octaves', tab='Noise', text='5')
        self.add_text_input('amp_m', 'Amplitude (m)', tab='Noise', text='100')
        self.add_checkbox('ridge', 'Ridge', tab='Noise', state=False)

        # --- ИСПРАВЛЕНИЕ: Используем правильное имя метода 'add_combo_menu' ---
        self.add_combo_menu('blend_mode', 'Blend Mode', items=['add', 'subtract', 'multiply'], tab='Blending')


    def compute(self, context):
        # Получаем данные с предыдущей ноды
        height_in_port = self.get_input(0)
        if height_in_port and height_in_port.connected_ports():
            source_node = height_in_port.connected_ports()[0].node()
            previous_height = source_node.compute(context)
        else:
            # Если ничего не подключено, начинаем с нуля
            previous_height = np.zeros_like(context["x_coords"])

        # --- НОВАЯ ЛОГИКА ВАРПИНГА ---
        warp_port = self.get_input(1)
        local_context = context.copy() # Создаем локальную копию контекста

        if warp_port and warp_port.connected_ports():
            print("  -> [NoiseNode] Warp field connected. Applying warp...")
            warp_node = warp_port.connected_ports()[0].node()
            warp_field = warp_node.compute(context)

            if warp_field and 'warp_x' in warp_field and 'warp_z' in warp_field:
                # Применяем смещение к координатам
                warped_x = local_context['x_coords'] + warp_field['warp_x']
                warped_z = local_context['z_coords'] + warp_field['warp_z']

                # Обновляем координаты в локальном контексте для этой ноды
                local_context['x_coords'] = warped_x
                local_context['z_coords'] = warped_z

        # --- Старая логика генерации шума (теперь работает с warped координатами) ---
        def _f(name, default):
            v = self.get_property(name)
            try: return float(v)
            except (ValueError, TypeError): return default

        def _i(name, default):
            v = self.get_property(name)
            try: return int(v)
            except (ValueError, TypeError): return default

        params = {
            "scale_tiles": _f('scale_tiles', 1500.0),
            "octaves": _i('octaves', 5),
            "ridge": bool(self.get_property('ridge')),
            "amp_m": _f('amp_m', 100.0),
            "seed_offset": _i('seed_offset', 0),
            "additive_only": self.get_property('blend_mode') != 'multiply',
        }

        # ВАЖНО: передаем local_context с измененными координатами
        noise_map = _generate_noise_field(params, local_context)

        # Смешиваем результат
        blend_mode = self.get_property('blend_mode')
        if blend_mode == 'add':
            final_map = previous_height + noise_map
        elif blend_mode == 'subtract':
            final_map = previous_height - noise_map
        elif blend_mode == 'multiply':
            # Нормализуем шум к [0, inf) для умножения
            amp = params["amp_m"]
            if amp > 1e-6:
                norm_noise = (noise_map / amp + 1.0)
            else:
                norm_noise = np.ones_like(noise_map)
            final_map = previous_height * norm_noise
        else:
            final_map = previous_height + noise_map

        self._result_cache = final_map
        return self._result_cache