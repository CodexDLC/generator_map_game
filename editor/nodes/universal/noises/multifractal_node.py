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
        # UI остается без изменений
        self.add_enum_input("noise_type", "Noise Type", ["FBM", "Ridged", "Billowy"], group="Fractal", default="FBM")
        self.add_float_input("scale", "Scale (%)", value=0.5, group="Fractal")
        self.add_text_input("octaves", "Octaves", group="Fractal", text="8")
        self.add_float_input("roughness", "Roughness (0..1)", value=0.5, group="Fractal")
        self.add_seed_input("seed", "Seed", group="Fractal")
        self.add_text_input("variation", "Variation", group="Variation", text="2.0")
        self.add_text_input("smoothness", "Smoothness", group="Variation", text="0.0")
        self.add_text_input("offset_x", "Offset X", group="Position", text="0.0")
        self.add_text_input("offset_y", "Offset Y", group="Position", text="0.0")
        self.add_text_input("scale_x", "Scale X", group="Position", text="1.0")
        self.add_text_input("scale_y", "Scale Y", group="Position", text="1.0")
        self.add_enum_input("warp_type", "Perturb", ["None", "Simple", "Complex"], group="Warp", default="None")
        self.add_float_input("warp_freq", "Frequency", group="Warp", value=0.05)
        self.add_float_input("warp_amp", "Amplitude (0..1)", group="Warp", value=0.5)
        self.add_text_input("warp_octaves", "Octaves", group="Warp", text="4")
        self.set_color(80, 25, 30)

    def _compute(self, context):
        # Собираем параметры как и раньше
        fractal_params = {
            'type': self.get_property('noise_type').lower(),
            'scale': self.get_property('scale'),
            'octaves': self.get_property('octaves'),
            'roughness': self.get_property('roughness'),
            'seed': self.get_property('seed'),
        }
        variation_params = {
            'variation': self.get_property('variation'),
            'smoothness': self.get_property('smoothness'),
        }
        position_params = {
            'offset_x': self.get_property('offset_x'),
            'offset_y': self.get_property('offset_y'),
            'scale_x': self.get_property('scale_x'),
            'scale_y': self.get_property('scale_y'),
        }
        warp_params = {
            'type': self.get_property('warp_type').lower(),
            'frequency': self.get_property('warp_freq'),
            'amplitude': self.get_property('warp_amp'),
            'octaves': self.get_property('warp_octaves'),
            'seed': self.get_property('seed'), # Можно использовать тот же сид
        }

        # ИЗМЕНЕНИЕ: Вызываем новую единую функцию-обертку
        result = multifractal_wrapper(context, fractal_params, variation_params, position_params, warp_params)
        self._result_cache = result
        return result
