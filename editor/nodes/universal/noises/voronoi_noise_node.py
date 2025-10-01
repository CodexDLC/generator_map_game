# editor/nodes/universal/noises/voronoi_noise_node.py
from editor.nodes.base_node import GeneratorNode
from generator_logic.terrain.voronoi import voronoi_noise_wrapper

class VoronoiNoiseNode(GeneratorNode):
    __identifier__ = "Универсальные.Шумы"
    NODE_NAME = "Voronoi"

    def __init__(self):
        super().__init__()
        self.add_output('Out')

        # --- Noise ---
        self.add_float_input("scale", "Scale (%)", value=0.5, tab="Params", group="Noise")
        self.add_float_input("jitter", "Jitter (0..1)", value=0.45, tab="Params", group="Noise")
        self.add_enum_input("function", "Function", ["F1", "F2", "F2-F1"], tab="Params", group="Noise", default="F1")
        self.add_float_input("gain", "Gain (0..1)", value=0.5, tab="Params", group="Noise")
        self.add_float_input("clamp_val", "Clamp (0..1)", value=0.1, tab="Params", group="Noise")
        self.add_seed_input("seed", "Seed", tab="Params", group="Noise")

        # --- Style / Metric / Terrace (новое) ---
        self.add_enum_input(
            "style", "Style",
            ["Cells (C)", "Ridges (R)", "Peaks (P)", "Plateaus (A)", "Mountains/Dual (D)"],
            tab="Params", group="Noise", default="Mountains/Dual (D)"
        )
        self.add_enum_input(
            "metric", "Metric",
            ["Euclidean", "Manhattan", "Chebyshev"],
            tab="Params", group="Noise", default="Euclidean"
        )
        self.add_text_input("terrace_steps", "Terrace Steps", tab="Params", group="Noise", text="8")
        self.add_float_input("terrace_blend", "Terrace Blend (0..1)", value=0.35, tab="Params", group="Noise")

        # --- Warp ---
        self.add_enum_input("warp_type", "Type", ["None", "Simple", "Complex"],
                            tab="Params", group="Warp", default="None")
        self.add_float_input("warp_freq", "Frequency", value=0.05, tab="Params", group="Warp")
        self.add_float_input("warp_amp", "Amplitude (0..1)", value=0.5, tab="Params", group="Warp")
        self.add_text_input("warp_octaves", "Octaves", tab="Params", group="Warp", text="14")

        self.set_color(90, 90, 30)

    # --- helpers (как у тебя) ---
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
        # распарсим style/metric из подписей enum
        style = str(self.get_property('style')).lower()
        metric = str(self.get_property('metric')).lower()
        if '(' in style:  # "Mountains/Dual (D)" -> "mountains/dual"
            style = style.split('(')[0].strip()
        if '(' in metric:
            metric = metric.split('(')[0].strip()

        noise_params = {
            'scale': self._get_float_param('scale', 0.5),
            'jitter': self._get_float_param('jitter', 0.45),
            'function': str(self.get_property('function')).lower(),
            'gain': self._get_float_param('gain', 0.5),
            'clamp': self._get_float_param('clamp_val', 0.1),  # ключ 'clamp' ждёт враппер
            'seed': self._get_int_param('seed', 0),
            # новое
            'style': style,
            'metric': metric,
            'terrace_steps': self._get_int_param('terrace_steps', 8),
            'terrace_blend': self._get_float_param('terrace_blend', 0.35),
        }

        warp_params = {
            'type': str(self.get_property('warp_type')).lower(),
            'frequency': self._get_float_param('warp_freq', 0.05),
            'amplitude': self._get_float_param('warp_amp', 0.5),
            'octaves': self._get_int_param('warp_octaves', 14),
        }

        result = voronoi_noise_wrapper(context, noise_params, warp_params)
        self._result_cache = result
        return result
