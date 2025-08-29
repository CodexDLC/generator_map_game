
from __future__ import annotations
from typing import Tuple
from .state import WorldState
from ...services.worldgen import generate_or_load
import pathlib

class WorldController:
    def __init__(self, state: WorldState):
        self.s = state

    def load_center(self) -> dict:
        k = self.s.key()
        if k in self.s.cache:
            return self.s.cache[k]
        data = generate_or_load(self.s.seed, self.s.cx, self.s.cz, pathlib.Path(self.s.preset_path))
        self.s.cache[k] = data
        return data

    def move(self, dx: int, dz: int) -> dict:
        self.s.cx += dx
        self.s.cz += dz
        return self.load_center()

    def get_neighbor(self, dcx: int, dcz: int) -> dict:
        key = (self.s.cx + dcx, self.s.cz + dcz)
        if key in self.s.cache:
            return self.s.cache[key]
        data = generate_or_load(self.s.seed, key[0], key[1], pathlib.Path(self.s.preset_path))
        self.s.cache[key] = data
        return data

    # --- ДОБАВЬ ЭТО НИЖЕ ---

    @staticmethod
    def _side_from_delta(dx: int, dz: int) -> str:
        if dz == -1: return "N"
        if dz ==  1: return "S"
        if dx == -1: return "W"
        if dx ==  1: return "E"
        raise ValueError("dx,dz must be one of (-1,0),(1,0),(0,-1),(0,1)")

    def can_move(self, dx: int, dz: int) -> bool:
        """Разрешаем шаг, только если есть порт здесь и у соседа на встречной стороне."""
        side = self._side_from_delta(dx, dz)
        center = self.load_center()
        if not (center.get("ports", {}).get(side) or []):
            return False  # у текущего нет порта
        neighbor = self.get_neighbor(dx, dz)  # префетчнем
        opposite = {"N":"S", "S":"N", "W":"E", "E":"W"}[side]
        return bool(neighbor.get("ports", {}).get(opposite) or [])