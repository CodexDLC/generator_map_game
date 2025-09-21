# stateless_rng.py
def u32(n: int) -> int: return n & 0xFFFFFFFF

def hash32(x: int, y: int, layer_seed: int) -> int:
    h = u32(0x9E3779B9 ^ layer_seed)
    h = u32(h ^ (x * 0x85EBCA6B) ^ (y * 0xC2B2AE35))
    h ^= (h >> 16); h = u32(h * 0x85EBCA6B)
    h ^= (h >> 13); h = u32(h * 0xC2B2AE35)
    h ^= (h >> 16)
    return h

def rnd01(x: int, y: int, layer_seed: int) -> float:
    return hash32(x, y, layer_seed) / 0xFFFFFFFF
