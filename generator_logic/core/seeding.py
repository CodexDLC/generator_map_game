# generator_logic/terrain/core/seeding.py
from __future__ import annotations

def _resolve_world_seed(context: dict) -> int:
    proj = context.get('project') or {}
    return int(context.get('WORLD_SEED', proj.get('world_seed', proj.get('seed', 0))))

def _mix_seed(world_seed: int, node_offset: int, salt: int) -> int:
    s = (world_seed ^ (node_offset * 0x9E3779B9) ^ salt) & 0xFFFFFFFF
    # xorshift на 32 битах
    s ^= (s << 13) & 0xFFFFFFFF
    s ^= (s >> 17)
    s ^= (s << 5) & 0xFFFFFFFF
    return s & 0x7FFFFFFF
