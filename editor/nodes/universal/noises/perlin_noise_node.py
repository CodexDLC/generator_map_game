# editor/nodes/universal/noises/perlin_noise_node.py
import numpy as np
from editor.nodes.base_node import GeneratorNode
from generator_logic.terrain.perlin import fbm_noise_wrapper


class PerlinNoiseNode(GeneratorNode):
    __identifier__ = "Универсальные.Шумы"
    NODE_NAME = "Perlin"

    def __init__(self):
        super().__init__()
        self.add_output('Out')

        # --- Group "Noise" ---
        self.add_enum_input("noise_type", "Type", ["FBM", "Ridged", "Billowy"], tab="Params", group="Noise",
                            default="FBM")
        self.add_float_input("scale", "Scale (%)", value=0.5, tab="Params", group="Noise", p_range=(0.0, 1.0),
                             p_widget='slider')
        self.add_text_input("octaves", "Octaves", tab="Params", group="Noise", text="8")
        self.add_float_input("gain", "Gain (0..1)", value=0.5, tab="Params", group="Noise", p_range=(0.0, 1.0),
                             p_widget='slider')
        self.add_float_input("amplitude", "Amplitude (0..1)", value=0.5, tab="Params", group="Noise",
                             p_range=(0.0, 1.0), p_widget='slider')
        self.add_seed_input("seed", "Seed", tab="Params", group="Noise")

        # --- Group "Warp" (Unified like Gaea) ---
        self.add_enum_input("warp_type", "Type", ["None", "Simple", "Complex"], tab="Params", group="Warp", default="None")
        self.add_float_input("warp_rel_size", "Relative Size", value=1.0, tab="Params", group="Warp",
                             p_range=(0.05, 8.0), p_widget='slider')
        self.add_float_input("warp_strength", "Strength", value=0.5, tab="Params", group="Warp",
                             p_range=(0.0, 1.0), p_widget='slider')
        self.add_text_input("warp_complexity", "Complexity", text='3', tab="Params", group="Warp")
        self.add_float_input("warp_roughness", "Roughness", value=0.5, tab="Params", group="Warp",
                             p_range=(0.0, 1.0), p_widget='slider')
        self.add_float_input("warp_attenuation", "Attenuation", value=0.5, tab="Params", group="Warp",
                             p_range=(0.0, 1.0), p_widget='slider')
        self.add_text_input("warp_iterations", "Iterations", text='3', tab="Params", group="Warp")
        self.add_float_input("warp_anisotropy", "Relative Anisotropy", value=1.0, tab="Params", group="Warp",
                             p_range=(0.2, 5.0), p_widget='slider')


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
        noise_params = {
            'type': self.get_property('noise_type').lower(),
            'scale': self._get_float_param('scale', 0.5),
            'octaves': self._get_int_param('octaves', 8),
            'gain': self._get_float_param('gain', 0.5),
            'amplitude': self._get_float_param('amplitude', 0.5),
            'seed': self.get_property('seed'),
        }

        # внутри _compute(self, context):
        world_size = context.get('WORLD_SIZE_METERS', 5000.0)
        max_height = (context.get('project') or {}).get('height_max_m', 1200.0)

        # сила основного шума в метрах (референс для Strength)
        main_noise_amplitude_m = noise_params['amplitude'] * max_height

        wt = str(self.get_property('warp_type')).lower()
        wr = {
            'type': wt,
            'rel_size': self._get_float_param('warp_rel_size', 1.0),
            'strength': self._get_float_param('warp_strength', 0.5),
            'complexity': self._get_int_param('warp_complexity', 3),
            'roughness': self._get_float_param('warp_roughness', 0.5),
            'attenuation': self._get_float_param('warp_attenuation', 0.5),
            'iterations': self._get_int_param('warp_iterations', 3),
            'anisotropy': self._get_float_param('warp_anisotropy', 1.0),
        }

        # Simple → фиксация параметров
        if wt == 'simple':
            wr['complexity']  = 1
            wr['roughness']   = 0.5
            wr['attenuation'] = 1.0
            wr['iterations']  = 1
            wr['anisotropy']  = 1.0

        # физические величины
        warp_freq = 1.0 / (world_size * max(wr['rel_size'], 1e-6))
        warp_amp0_m = wr['strength'] * main_noise_amplitude_m

        warp_params_final = {
            'type': wt,
            'frequency': warp_freq,
            'amp0_m': warp_amp0_m,
            'complexity': wr['complexity'],
            'roughness': wr['roughness'],
            'attenuation': wr['attenuation'],
            'iterations': wr['iterations'],
            'anisotropy': wr['anisotropy'],
            'seed': noise_params['seed']
        }
        result = fbm_noise_wrapper(context, noise_params, warp_params_final)

        self._result_cache = result
        return result