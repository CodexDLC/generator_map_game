# editor/nodes/universal/noises/multifractal_node.py
from editor.nodes.base_node import GeneratorNode
from generator_logic.terrain.fractals import multifractal_wrapper

class MultiFractalNode(GeneratorNode):
    __identifier__ = "Универсальные.Шумы"
    NODE_NAME = "MultiFractal"

    def __init__(self):
        super().__init__()
        self.add_output('Out')

        # --- Fractal ---
        self.add_enum_input("noise_type", "Noise Type", ["FBM", "Ridged", "Billowy"], group="Fractal", default="FBM", tab="Params")
        self.add_float_input("scale", "Scale (0..1)", value=0.5, group="Fractal", p_range=(0.0, 1.0), p_widget='slider', tab="Params")
        self.add_text_input("octaves", "Octaves", group="Fractal", text="8", tab="Params")
        self.add_float_input("roughness", "Roughness (0..1)", value=0.5, group="Fractal", p_range=(0.0, 1.0), p_widget='slider', tab="Params")
        self.add_seed_input("seed", "Seed", group="Fractal", tab="Params")

        # --- Variation ---
        self.add_float_input("var_strength", "Variation", value=1.0, group="Variation", p_range=(0.0, 4.0), p_widget='slider', tab="Params")
        self.add_float_input("var_smoothness", "Smoothness", value=0.0, group="Variation", p_range=(-20.0, 20.0), p_widget='slider', tab="Params")
        self.add_float_input("var_contrast", "Contrast", value=0.3, group="Variation", p_range=(0.0, 1.0), p_widget='slider', tab="Params")
        self.add_float_input("var_damping", "Damping (0..1)", value=0.25, group="Variation", p_range=(0.0, 1.0), p_widget='slider', tab="Params")
        self.add_float_input("var_bias", "Bias (-1..1)", value=0.5, group="Variation", p_range=(0.0, 1.0), p_widget='slider', tab="Params")

        # --- Position ---
        self.add_text_input("offset_x", "Offset X", group="Position", text="0.0", tab="Params")
        self.add_text_input("offset_y", "Offset Y", group="Position", text="0.0", tab="Params")
        self.add_text_input("scale_x", "Scale X", group="Position", text="1.0", tab="Params")
        self.add_text_input("scale_y", "Scale Y", group="Position", text="1.0", tab="Params")

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

        self.set_color(80, 25, 30)

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
        fractal_params = {
            'type': self.get_property('noise_type').lower(),
            'scale': self._get_float_param('scale', 0.5),
            'octaves': self._get_int_param('octaves', 8),
            'roughness': self._get_float_param('roughness', 0.5),
            'seed': self._get_int_param('seed', 0),
        }
        variation_params = {
            'variation': self._get_float_param('var_strength', 1.0),
            'smoothness': self._get_float_param('var_smoothness', 0.0),
            'contrast': self._get_float_param('var_contrast', 0.3),
            'damping': self._get_float_param('var_damping', 0.25),
            'bias': self._get_float_param('var_bias', 0.5),
        }
        position_params = {
            'offset_x': self._get_float_param('offset_x', 0.0),
            'offset_y': self._get_float_param('offset_y', 0.0),
            'scale_x': self._get_float_param('scale_x', 1.0),
            'scale_y': self._get_float_param('scale_y', 1.0),
        }

        world_size = context.get('WORLD_SIZE_METERS', 5000.0)
        max_height = (context.get('project') or {}).get('height_max_m', 1200.0)
        reference_height_m = max_height

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

        if wt == 'simple':
            wr['complexity']  = 1
            wr['roughness']   = 0.5
            wr['attenuation'] = 1.0
            wr['iterations']  = 1
            wr['anisotropy']  = 1.0

        warp_freq = 1.0 / (world_size * max(wr['rel_size'], 1e-6))
        warp_amp0_m = wr['strength'] * reference_height_m

        warp_params_final = {
            'type': wt,
            'frequency': warp_freq,
            'amp0_m': warp_amp0_m,
            'complexity': wr['complexity'],
            'roughness': wr['roughness'],
            'attenuation': wr['attenuation'],
            'iterations': wr['iterations'],
            'anisotropy': wr['anisotropy'],
            'seed': fractal_params['seed']
        }

        result = multifractal_wrapper(context, fractal_params, variation_params, position_params, warp_params_final)
        self._result_cache = result
        return result
