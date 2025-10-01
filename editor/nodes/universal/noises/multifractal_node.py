# editor/nodes/universal/noises/multifractal_node.py
from editor.nodes.base_node import GeneratorNode
# ИЗМЕНЕНИЕ: импортируем новую обертку
from generator_logic.terrain.fractals import multifractal_wrapper

class MultiFractalNode(GeneratorNode):
    __identifier__ = "Универсальные.Шумы"
    NODE_NAME = "MultiFractal"

    def __init__(self):
        super().__init__()
        self.add_output('Out')

        # --- НАЧАЛО ИЗМЕНЕНИЯ: Новая структура UI ---
        # --- Fractal ---
        self.add_enum_input("noise_type", "Noise Type", ["FBM", "Ridged", "Billowy"], group="Fractal", default="FBM")
        self.add_float_input("scale", "Scale (0..1)", value=0.5, group="Fractal")
        self.add_text_input("octaves", "Octaves", group="Fractal", text="8")
        self.add_float_input("roughness", "Roughness (0..1)", value=0.5, group="Fractal")
        self.add_seed_input("seed", "Seed", group="Fractal")

        # --- Variation ---
        self.add_float_input("var_strength", "Variation", value=2.0, group="Variation")
        self.add_float_input("var_smoothness", "Smoothness", value=0.0, group="Variation")
        self.add_float_input("var_contrast", "Contrast", value=0.3, group="Variation")
        self.add_float_input("var_damping", "Damping (0..1)", value=0.25, group="Variation")
        self.add_float_input("var_bias", "Bias (-1..1)", value=0.5, group="Variation")

        # --- Position ---
        self.add_text_input("offset_x", "Offset X", group="Position", text="0.0")
        self.add_text_input("offset_y", "Offset Y", group="Position", text="0.0")
        self.add_text_input("scale_x", "Scale X", group="Position", text="1.0")
        self.add_text_input("scale_y", "Scale Y", group="Position", text="1.0")

        # --- Warp ---
        self.add_enum_input("warp_type", "Perturb", ["None", "Simple", "Complex"], group="Warp", default="None")
        self.add_float_input("warp_freq", "Frequency", group="Warp", value=0.05)
        self.add_float_input("warp_amp", "Amplitude (0..1)", group="Warp", value=0.5)
        self.add_text_input("warp_octaves", "Octaves", group="Warp", text="4")
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

        self.set_color(80, 25, 30)

    def _compute(self, context):
        # Собираем параметры как и раньше, но теперь их больше
        fractal_params = {
            'type': self.get_property('noise_type').lower(),
            'scale': self.get_property('scale'),
            'octaves': self.get_property('octaves'),
            'roughness': self.get_property('roughness'),
            'seed': self.get_property('seed'),
        }
        variation_params = {
            'variation': self.get_property('var_strength'),
            'smoothness': self.get_property('var_smoothness'),
            'contrast': self.get_property('var_contrast'),
            'damping': self.get_property('var_damping'),
            'bias': self.get_property('var_bias'),
        }
        position_params = {
            'offset_x': self.get_property('offset_x'),
            'offset_y': self.get_property('offset_y'),
            'scale_x': self.get_property('scale_x'), # <- Убедитесь, что эти строки есть
            'scale_y': self.get_property('scale_y'), # <- Убедитесь, что эти строки есть
        }
        warp_params = {
            'type': self.get_property('warp_type').lower(),
            'frequency': self.get_property('warp_freq'),
            'amplitude': self.get_property('warp_amp'),
            'octaves': self.get_property('warp_octaves'),
        }

        result = multifractal_wrapper(context, fractal_params, variation_params, position_params, warp_params)
        self._result_cache = result
        return result
