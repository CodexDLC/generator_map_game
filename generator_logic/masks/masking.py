# generator_logic/masks/masking.py
from __future__ import annotations
import numpy as np

def _smoothstep(edge0, edge1, x):
    """Helper for smooth transitions."""
    denom = max(float(edge1 - edge0), 1e-9)
    t = np.clip((x - edge0) / denom, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)

def create_slope_mask(
    context: dict,
    height_map_01: np.ndarray,
    min_angle_deg: float,
    max_angle_deg: float,
    edge_softness_deg: float,
    invert: bool
) -> np.ndarray:
    """
    Creates a mask based on the slope of the terrain.

    Args:
        context: The global context containing world settings.
        height_map_01: The input height map, normalized to [0..1].
        min_angle_deg: The minimum angle of the slope range in degrees.
        max_angle_deg: The maximum angle of the slope range in degrees.
        edge_softness_deg: The softness of the transition at the edges of the range.
        invert: Whether to invert the final mask.

    Returns:
        A NumPy array (float32) representing the slope mask [0..1].
    """
    if not isinstance(height_map_01, np.ndarray):
        # If no input, return a black mask
        return np.zeros(context['x_coords'].shape, dtype=np.float32)

    world_settings = context.get('world_settings', {})
    max_height = world_settings.get('max_height', 1000.0)
    vertex_spacing = world_settings.get('vertex_spacing', 1.0)

    # Convert normalized height map to meters for accurate gradient calculation
    hmap_meters = height_map_01 * max_height

    # Ensure parameters are valid
    soft_deg = max(edge_softness_deg, 0.0)
    if max_angle_deg < min_angle_deg:
        min_angle_deg, max_angle_deg = max_angle_deg, min_angle_deg

    # Calculate gradient considering physical units (vertex_spacing)
    # The order is (gradient along axis 0 (z), gradient along axis 1 (x))
    dz, dx = np.gradient(hmap_meters, vertex_spacing, vertex_spacing)
    
    # Calculate slope magnitude |∇h|
    slope_magnitude = np.hypot(dx, dz)
    
    # Convert slope to angle in degrees
    angle_deg = np.degrees(np.arctan(slope_magnitude))

    # Create mask using smoothstep for soft transitions
    lower_bound = _smoothstep(min_angle_deg - soft_deg, min_angle_deg + soft_deg, angle_deg)
    upper_bound = 1.0 - _smoothstep(max_angle_deg - soft_deg, max_angle_deg + soft_deg, angle_deg)
    mask = np.clip(lower_bound * upper_bound, 0.0, 1.0)

    if invert:
        mask = 1.0 - mask

    return mask.astype(np.float32)
