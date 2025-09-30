# editor/nodes/universal/noises/voronoi_noise_node.py
from editor.nodes.base_node import GeneratorNode
from generator_logic.terrain.noises import voronoi_noise_wrapper

class VoronoiNoiseNode(GeneratorNode):
    __identifier__ = "Универсальные.Шумы"
    NODE_NAME = "Voronoi"

    def __init__(self):
        super().__init__()
        self.add_output('Out')

        # Group "Noise"
        self.add_text_input("scale", "Scale", tab="Params", group="Noise", text="0.5")
        self.add_text_input("jitter", "Jitter", tab="Params", group="Noise", text="0.45")
        self.add_enum_input("function", "Function", ["F1", "F2", "F2-F1"], tab="Params", group="Noise", default="F1")
        self.add_text_input("gain", "Gain", tab="Params", group="Noise", text="0.5")
        self.add_text_input("clamp_val", "Clamp", tab="Params", group="Noise", text="0.5")
        self.add_seed_input("seed", "Seed", tab="Params", group="Noise")

        # Group "Warp"
        self.add_enum_input("warp_type", "Type", ["None", "Simple", "Complex"], tab="Params", group="Warp", default="None")
        self.add_text_input("warp_freq", "Frequency", tab="Params", group="Warp", text="0.05")
        self.add_text_input("warp_amp", "Amplitude", tab="Params", group="Warp", text="0.5")
        self.add_text_input("warp_octaves", "Octaves", tab="Params", group="Warp", text="14")

        self.set_color(90, 90, 30)

    def _get_float_param(self, name: str, default: float) -> float:
        try:
            return float(self.get_property(name))
        except (ValueError, TypeError):
            return default

    def _get_int_param(self, name: str, default: int) -> int:
        try:
            return int(self.get_property(name))
        except (ValueError, TypeError):
            return default

    def _compute(self, context):
        noise_params = {
            'scale': self._get_float_param('scale', 0.5),
            'jitter': self._get_float_param('jitter', 0.45),
            'function': self.get_property('function').lower(),
            'gain': self._get_float_param('gain', 0.5),
            'clamp': self._get_float_param('clamp_val', 0.5),
            'seed': self.get_property('seed'),
        }
        warp_params = {
            'type': self.get_property('warp_type').lower(),
            'frequency': self._get_float_param('warp_freq', 0.05),
            'amplitude': self._get_float_param('warp_amp', 0.5),
            'octaves': self._get_int_param('warp_octaves', 14),
        }

        result = voronoi_noise_wrapper(context, noise_params, warp_params)
        self._result_cache = result
        return result
