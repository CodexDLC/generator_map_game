# ==============================================================================
# Файл: editor/nodes/warp_node.py
# ВЕРСИЯ 1.1: Добавлено раздельное управление силой по осям X и Z.
# ==============================================================================
from editor.nodes.base_node import GeneratorNode
from game_engine_restructured.algorithms.terrain.steps.noise import _generate_noise_field

class WarpNode(GeneratorNode):
    __identifier__ = 'Ландшафт.Модули'
    NODE_NAME = 'Warp'

    def __init__(self):
        super().__init__()
        self.add_output('warp_field')

        # --- ИЗМЕНЕНИЕ: Разделяем амплитуду на X и Z ---
        self.add_text_input('amp_x', 'Amplitude X (m)', tab='Warp Settings', text='200.0')
        self.add_text_input('amp_z', 'Amplitude Z (m)', tab='Warp Settings', text='200.0')
        self.add_text_input('scale_tiles', 'Scale (tiles)', tab='Warp Settings', text='4000')
        self.add_text_input('octaves', 'Octaves', tab='Warp Settings', text='2')

        self.set_color(25, 80, 30)

    def compute(self, context):
        print("  -> [WarpNode] Computing directional warp field...")

        def _f(name, default):
            v = self.get_property(name)
            try: return float(v)
            except (ValueError, TypeError): return default

        def _i(name, default):
            v = self.get_property(name)
            try: return int(v)
            except (ValueError, TypeError): return default

        # --- ИЗМЕНЕНИЕ: Собираем параметры для X и Z отдельно ---
        base_params = {
            "scale_tiles": _f('scale_tiles', 4000.0),
            "octaves": _i('octaves', 2),
            "ridge": False,
            "additive_only": False
        }

        # Параметры для смещения по X
        params_x = base_params.copy()
        params_x["amp_m"] = _f('amp_x', 200.0)
        params_x["seed_offset"] = 0

        # Параметры для смещения по Z
        params_z = base_params.copy()
        params_z["amp_m"] = _f('amp_z', 200.0)
        params_z["seed_offset"] = 1 # Другой сид для независимости

        warp_x = _generate_noise_field(params_x, context)
        warp_z = _generate_noise_field(params_z, context)

        self._result_cache = {'warp_x': warp_x, 'warp_z': warp_z}
        return self._result_cache