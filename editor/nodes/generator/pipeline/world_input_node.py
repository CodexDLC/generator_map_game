# ==============================================================================
# Файл: editor/nodes/world_input_node.py
# ВЕРСИЯ 2.0: Добавлен вход для искажения (warp).
# ==============================================================================
import numpy as np
from editor.nodes.base_node import GeneratorNode
from game_engine_restructured.algorithms.terrain.steps.noise import _generate_noise_field

class WorldInputNode(GeneratorNode):
    __identifier__ = 'generator.pipeline'
    NODE_NAME = 'World Input'

    def __init__(self):
        super().__init__()

        # --- ИЗМЕНЕНИЕ: Добавляем вход для варпа ---
        self.add_input('warp_field', 'Warp Field (optional)')
        self.add_output('height')

        # Параметры остаются прежними
        self.add_text_input('scale_tiles', 'Scale (tiles)', tab='Continental Noise', text='6000')
        self.add_text_input('octaves', 'Octaves', tab='Continental Noise', text='3')
        self.add_text_input('amp_m', 'Amplitude (m)', tab='Continental Noise', text='400')
        self.add_checkbox('ridge', 'Ridge', tab='Continental Noise', state=False)

        self.set_color(80, 25, 30)

    def compute(self, context):
        """
        Генерирует "сырой" ландшафт, теперь с возможностью искажения координат.
        """
        # --- ИЗМЕНЕНИЕ: Добавляем логику варпинга, как в NoiseNode ---
        warp_port = self.get_input(0)
        local_context = context.copy() # Работаем с локальной копией

        if warp_port and warp_port.connected_ports():
            print("  -> [WorldInput] Warp field connected. Applying warp...")
            warp_node = warp_port.connected_ports()[0].node()
            warp_field = warp_node.compute(context)

            if warp_field and 'warp_x' in warp_field and 'warp_z' in warp_field:
                warped_x = local_context['x_coords'] + warp_field['warp_x']
                warped_z = local_context['z_coords'] + warp_field['warp_z']
                local_context['x_coords'] = warped_x
                local_context['z_coords'] = warped_z
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

        def _f(name, default):
            v = self.get_property(name)
            try: return float(v)
            except (ValueError, TypeError): return default

        def _i(name, default):
            v = self.get_property(name)
            try: return int(v)
            except (ValueError, TypeError): return default

        noise_params = {
            "scale_tiles": _f('scale_tiles', 6000.0),
            "octaves": _i('octaves', 3),
            "amp_m": _f('amp_m', 400.0),
            "ridge": bool(self.get_property('ridge')),
            "seed_offset": 0,
            "blend_mode": "replace"
        }

        # Вызываем генератор с возможно измененным local_context
        height_map = _generate_noise_field(noise_params, local_context)

        self._result_cache = height_map
        return self._result_cache