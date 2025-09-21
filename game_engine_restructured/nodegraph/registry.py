# game_engine_restructured/nodegraph/registry.py

# Каждая фабрика должна возвращать callable:
#    fn(ctx, inputs) -> dict(outputs)
# где inputs/outputs — словари с numpy-массивами (например, {"height": np.ndarray})

from ..algorithms.terrain  import node_noise
from ..algorithms.terrain.noise     import node_masked_noise
from ..algorithms.terrain.stamping  import node_walker_stampede
from ..algorithms.terrain.effects   import node_selective_smoothing

REGISTRY = {
    "noise":                node_noise,
    "masked_noise":         node_masked_noise,
    "walker_stampede":      node_walker_stampede,
    "selective_smoothing":  node_selective_smoothing,
}
