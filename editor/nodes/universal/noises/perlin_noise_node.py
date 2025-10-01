# editor/nodes/universal/noises/perlin_noise_node.py
from editor.nodes.base_node import GeneratorNode
from generator_logic.terrain.perlin import fbm_noise_wrapper

class PerlinNoiseNode(GeneratorNode):
    __identifier__ = "Универсальные.Шумы"
    NODE_NAME = "Perlin"

    def __init__(self):
        super().__init__()
        self.add_output('Out')

        # Group "Noise"
        self.add_enum_input("noise_type", "Type", ["FBM", "Ridged", "Billowy"], tab="Params", group="Noise", default="FBM")
        self.add_float_input("scale", "Scale (%)", value=0.1, tab="Params", group="Noise")
        self.add_text_input("octaves", "Octaves", tab="Params", group="Noise", text="10")
        self.add_float_input("gain", "Gain (0..1)", value=0.5, tab="Params", group="Noise")
        self.add_float_input("amplitude", "Amplitude (0..1)", value=1.0, tab="Params", group="Noise")
        self.add_seed_input("seed", "Seed", tab="Params", group="Noise")

        # Group "Warp"
        self.add_enum_input("warp_type", "Type", ["None", "Simple", "Complex"], tab="Params", group="Warp", default="None")
        self.add_float_input("warp_freq", "Frequency", value=0.05, tab="Params", group="Warp")
        self.add_float_input("warp_amp", "Amplitude (0..1)", value=0.5, tab="Params", group="Warp")
        self.add_text_input("warp_octaves", "Octaves", tab="Params", group="Warp", text="10")

        self.set_color(90, 30, 90)

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
        # --- НАЧАЛО ИЗМЕНЕНИЯ ---
        world_size = context.get('WORLD_SIZE_METERS', 5000.0)
        relative_scale = self._get_float_param('scale', 0.1)

        # Рассчитываем абсолютный масштаб в метрах
        absolute_scale_in_meters = relative_scale * world_size
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

        noise_params = {
            'type': self.get_property('noise_type').lower(),
            'scale': absolute_scale_in_meters,  # <--- Передаем рассчитанное значение
            'octaves': self._get_int_param('octaves', 10),
            'gain': self._get_float_param('gain', 0.5),
            'amplitude': self.get_property('amplitude'),
            'seed': self.get_property('seed'),
        }
        warp_params = {
            'type': self.get_property('warp_type').lower(),
            'frequency': self._get_float_param('warp_freq', 0.05),
            'amplitude': self._get_float_param('warp_amp', 0.5),
            'octaves': self._get_int_param('warp_octaves', 10),
        }

        result = fbm_noise_wrapper(context, noise_params, warp_params)
        self._result_cache = result
        return result
