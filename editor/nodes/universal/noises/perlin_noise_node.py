# editor/nodes/universal/noises/perlin_noise_node.py
from editor.nodes.base_node import GeneratorNode
from generator_logic.terrain.noises import generate_fbm_noise

class PerlinNoiseNode(GeneratorNode):
    __identifier__ = "Универсальные.Шумы"
    NODE_NAME = "Perlin"

    def __init__(self):
        super().__init__()
        self.add_output('Out')

        # Group "Noise"
        self.add_enum_input("noise_type", "Type", ["FBM", "Ridged", "Billowy"], tab="Params", group="Noise", default="FBM")
        self.add_text_input("scale", "Scale", tab="Params", group="Noise", text="0.5")
        self.add_text_input("octaves", "Octaves", tab="Params", group="Noise", text="10")
        self.add_text_input("gain", "Gain", tab="Params", group="Noise", text="0.5")
        self.add_text_input("height", "Height", tab="Params", group="Noise", text="1.0")
        self.add_seed_input("seed", "Seed", tab="Params", group="Noise")

        # Group "Warp"
        self.add_enum_input("warp_type", "Type", ["None", "Simple", "Complex"], tab="Params", group="Warp", default="None")
        self.add_text_input("warp_freq", "Frequency", tab="Params", group="Warp", text="0.05")
        self.add_text_input("warp_amp", "Amplitude", tab="Params", group="Warp", text="0.5")
        self.add_text_input("warp_octaves", "Octaves", tab="Params", group="Warp", text="10")

        self.set_color(90, 30, 90)

    def _compute(self, context):
        noise_params = {
            'type': self.get_property('noise_type').lower(),
            'octaves': self.get_property('octaves'),
            'gain': self.get_property('gain'),
            'height': self.get_property('height'),
            'seed': self.get_property('seed'),
        }
        warp_params = {
            'type': self.get_property('warp_type').lower(),
            'frequency': self.get_property('warp_freq'),
            'amplitude': self.get_property('warp_amp'),
            'octaves': self.get_property('warp_octaves'),
            'seed': self.get_property('seed') + 12345, # Separate seed for warp
        }

        coords_x = context['x_coords'] * self.get_property('scale')
        coords_z = context['z_coords'] * self.get_property('scale')

        result = generate_fbm_noise(coords_x, coords_z, noise_params, warp_params)
        self._result_cache = result
        return result
