# editor/nodes/universal/noises/voronoi_noise_node.py
import numpy as np
from editor.nodes.base_node import GeneratorNode
from generator_logic.terrain.voronoi import voronoi_noise_wrapper


class VoronoiNoiseNode(GeneratorNode):
    __identifier__ = "Универсальные.Шумы"
    NODE_NAME = "Voronoi"

    def __init__(self):
        super().__init__()
        self.add_output('Out')

        # --- Noise ---
        self.add_float_input("scale", "Scale (%)", value=0.5, tab="Params", group="Noise",
                             p_range=(0.01, 4.0), p_widget='slider')
        self.add_float_input("jitter", "Jitter (0..1)", value=0.45, tab="Params", group="Noise",
                             p_range=(0.0, 1.0), p_widget='slider')
        self.add_enum_input("function", "Function", ["F1", "F2", "F2-F1"], tab="Params", group="Noise", default="F1")
        self.add_float_input("gain", "Gain (0..1)", value=0.5, tab="Params", group="Noise",
                             p_range=(0.0, 1.0), p_widget='slider')
        self.add_float_input("clamp_val", "Clamp (0..1)", value=0.1, tab="Params", group="Noise",
                             p_range=(0.0, 1.0), p_widget='slider')
        self.add_seed_input("seed", "Seed", tab="Params", group="Noise")

        self.add_enum_input("style", "Style",
                            ["Cells (C)", "Ridges (R)", "Peaks (P)", "Plateaus (A)", "Mountains/Dual (D)"],
                            tab="Params", group="Noise", default="Mountains/Dual (D)")
        self.add_enum_input("metric", "Metric", ["Euclidean", "Manhattan", "Chebyshev"], tab="Params", group="Noise",
                            default="Euclidean")
        self.add_text_input("terrace_steps", "Terrace Steps", tab="Params", group="Noise", text="8")
        self.add_float_input("terrace_blend", "Terrace Blend (0..1)", value=0.35, tab="Params", group="Noise",
                             p_range=(0.0, 1.0), p_widget='slider')

        # --- Warp (Gaea-style, единый стандарт) ---
        self.add_enum_input("warp_type", "Type", ["None", "Simple", "Complex"], tab="Params", group="Warp",
                            default="None")
        self.add_float_input("warp_rel_size", "Relative Size", value=1.0, tab="Params", group="Warp",
                             p_range=(0.05, 8.0), p_widget='slider')
        self.add_float_input("warp_strength", "Strength", value=0.5, tab="Params", group="Warp",
                             p_range=(0.0, 1.0), p_widget='slider')
        self.add_text_input("warp_complexity", "Complexity", text='3', tab="Params", group="Warp")
        self.add_float_input("warp_roughness", "Roughness", value=0.45, tab="Params", group="Warp",
                             p_range=(0.0, 1.0), p_widget='slider')
        self.add_float_input("warp_attenuation", "Attenuation", value=0.5, tab="Params", group="Warp",
                             p_range=(0.0, 1.0), p_widget='slider')
        self.add_text_input("warp_iterations", "Iterations", text='3', tab="Params", group="Warp")
        self.add_float_input("warp_anisotropy", "Relative Anisotropy", value=1.0, tab="Params", group="Warp",
                             p_range=(0.2, 5.0), p_widget='slider')

        self.set_color(90, 90, 30)

    # helpers
    def _get_float(self, name: str, default: float) -> float:
        try:
            return float(self.get_property(name))
        except (ValueError, TypeError):
            return default

    def _get_int(self, name: str, default: int) -> int:
        try:
            return int(self.get_property(name))
        except (ValueError, TypeError):
            return default

    def _compute(self, context):
        # --- санируем style/metric ---
        style = str(self.get_property('style')).lower()
        metric = str(self.get_property('metric')).lower()
        if '(' in style: style = style.split('(')[0].strip()
        if '(' in metric: metric = metric.split('(')[0].strip()

        # --- Noise params ---
        noise_params = {
            'scale': self._get_float('scale', 0.5),
            'jitter': self._get_float('jitter', 0.45),
            'function': str(self.get_property('function')).lower(),
            'gain': self._get_float('gain', 0.5),
            'clamp': self._get_float('clamp_val', 0.1),
            'seed': self._get_int('seed', 0),
            'style': style,
            'metric': metric,
            'terrace_steps': self._get_int('terrace_steps', 8),
            'terrace_blend': self._get_float('terrace_blend', 0.35),
        }

        # --- Warp UI → физика ---
        wt = str(self.get_property('warp_type')).lower()
        wr = {
            'type': wt,
            'rel_size': self._get_float('warp_rel_size', 1.0),
            'strength': self._get_float('warp_strength', 0.5),
            'complexity': self._get_int('warp_complexity', 3),
            'roughness': self._get_float('warp_roughness', 0.45),
            'attenuation': self._get_float('warp_attenuation', 0.5),
            'iterations': self._get_int('warp_iterations', 3),
            'anisotropy': self._get_float('warp_anisotropy', 1.0),
        }

        # Simple → фикс-параметры
        if wt == 'simple':
            wr['complexity']  = 1
            wr['roughness']   = 0.5
            wr['attenuation'] = 1.0
            wr['iterations']  = 1
            wr['anisotropy']  = 1.0

        world_size = context.get('WORLD_SIZE_METERS', 5000.0)
        max_height = (context.get('project') or {}).get('height_max_m', 1200.0)

        warp_freq = 1.0 / (world_size * max(wr['rel_size'], 1e-6))
        # Для Вороного нет "своей" амплитуды → опорой служит максимальная высота мира
        warp_amp0_m = wr['strength'] * max_height

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

        result = voronoi_noise_wrapper(context, noise_params, warp_params_final)
        self._result_cache = result
        return result
