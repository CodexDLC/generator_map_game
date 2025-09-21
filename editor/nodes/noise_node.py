from .base_node import GeneratorNode

class NoiseNode(GeneratorNode):
    __identifier__ = 'generator.nodes'
    NODE_NAME = 'Noise'

    def __init__(self):
        super().__init__()

        # создаём свойства ТОЛЬКО через add_* (они сами делают create_property)
        self.add_text_input('seed_offset', 'Seed offset', tab='Noise')
        self.add_text_input('scale_tiles', 'Scale (tiles or m)', tab='Noise')
        self.add_text_input('octaves', 'Octaves', tab='Noise')
        self.add_text_input('amp_m', 'Amplitude (m)', tab='Noise')
        self.add_checkbox('ridge', 'Ridge', tab='Noise')

        self.add_output('height')

    def compute(self, context=None):
        # не забывай приводить типы: text_input отдаёт строки
        def _f(name, default): 
            v = self.get_property(name)
            try:
                return float(v)
            except Exception:
                return float(default)

        def _i(name, default):
            v = self.get_property(name)
            try:
                return int(float(v))
            except Exception:
                return int(default)

        seed_offset = _i('seed_offset', 0)
        scale_tiles = _f('scale_tiles', 1500.0)
        octaves     = _i('octaves', 5)
        amp_m       = _f('amp_m', 800.0)
        ridge       = bool(self.get_property('ridge'))

        params = {
            "scale_tiles": scale_tiles,
            "octaves": octaves,
            "ridge": ridge,
            "amp_m": amp_m,
            "seed_offset": seed_offset,
            "additive_only": True,
            "shaping_power": 1.0,
            "warp": {}
        }

        from game_engine_restructured.algorithms.terrain.nodes.noise import _generate_noise_field
        h = _generate_noise_field(params, context)
        self._result_cache = h
        return h
