# game_engine/core/utils/rng.py
from __future__ import annotations
from typing import Union, List, Any, Dict

# golden ratio for 64-bit
_DEF_CONST = 0x9E3779B97F4A7C15

def _splitmix64(x: int) -> int:
    x = (x + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    z = x
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9 & 0xFFFFFFFFFFFFFFFF
    z = (z ^ (z >> 27)) * 0x94D049BB133111EB & 0xFFFFFFFFFFFFFFFF
    return z ^ (z >> 31)

def seed_from_any(x: Union[int, str, bytes]) -> int:
    if isinstance(x, int):
        return x & 0xFFFFFFFFFFFFFFFF
    if isinstance(x, bytes):
        acc = 0xcbf29ce484222325
        for b in x:
            acc ^= b
            acc = (acc * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
        return acc
    if isinstance(x, str):
        return seed_from_any(x.encode('utf-8'))
    raise TypeError("Unsupported seed type")

def hash64(*vals: int) -> int:
    h = 0x84222325CBF29CE4
    for v in vals:
        h ^= v & 0xFFFFFFFFFFFFFFFF
        h = _splitmix64(h)
    return h

def split_chunk_seed(seed: int, cx: int, cz: int) -> int:
    return hash64(seed, cx & 0xFFFFFFFFFFFFFFFF, cz & 0xFFFFFFFFFFFFFFFF)

def edge_key(seed: int, cx1: int, cz1: int, cx2: int, cz2: int, ) -> int:
    if (cx2, cz2) < (cx1, cz1):
        cx1, cz1, cx2, cz2 = cx2, cz2, cx1, cz1
    return hash64(seed ^ _DEF_CONST, cx1, cz1, cx2, cz2)

class RNG:
    __slots__ = ("state",)

    def __init__(self, seed: int):
        self.state = seed & 0xFFFFFFFFFFFFFFFF

    def u64(self) -> int:
        self.state = _splitmix64(self.state)
        return self.state

    def u32(self) -> int:
        return self.u64() >> 32

    def uniform(self) -> float:
        return (self.u64() >> 11) * (1.0 / (1 << 53))

    def randint(self, a: int, b: int) -> int:
        if a > b: a, b = b, a
        span = b - a + 1
        return a + (self.u64() % span)

    def choose(self, seq):
        return seq[self.u64() % len(seq)]

    def shuffle(self, seq: List[Any]) -> None:
        for i in range(len(seq) - 1, 0, -1):
            j = self.u64() % (i + 1)
            seq[i], seq[j] = seq[j], seq[i]

# <<< ВОТ ПРАВИЛЬНОЕ МЕСТО И ОТСТУП >>>
# Функция находится в файле, но вне класса RNG
def init_rng(seed: int, cx: int, cz: int) -> Dict[str, int]:
    """
    Создает детерминированные сиды для разных стадий генерации,
    основанные на глобальном сиде и координатах чанка.
    """
    base = split_chunk_seed(seed, cx, cz)
    return {
        "elevation":   seed,
        "temperature": seed ^ 0xA5A5A5A5,
        "humidity":    seed ^ 0x5A5A5A5A,
        # --- НАЧАЛО ИЗМЕНЕНИЙ ---
        "obstacles":   seed ^ 0x55AA55AA, # <-- Меняем 'base' на 'seed' и добавляем XOR, чтобы шум отличался от высот
        # --- КОНЕЦ ИЗМЕНЕНИЙ ---
        "water":       base ^ 0x33CC33CC,
    }