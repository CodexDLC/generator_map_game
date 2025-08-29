from __future__ import annotations
import json, pathlib, hashlib
from typing import Dict, Set
from .state import WorldState
from ...services.worldgen import generate_or_load


class WorldController:
    def __init__(self, state: WorldState):
        self.s = state
        self._branches = None          # конфиг ветвей из пресета
        self._city_gate_sides: Set[str] | None = None  # детермин. набор сторон-шлюзов

    # ---------- пресет ветвей ----------
    def _branches_cfg(self) -> Dict[str, dict]:
        if self._branches is not None:
            return self._branches
        p = pathlib.Path(self.s.preset_path)
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._branches = data.get("branches", {}) if isinstance(data, dict) else {}
        except Exception:
            self._branches = {}
        return self._branches

    # ---------- утилиты ----------
    @staticmethod
    def _side_from_delta(dx: int, dz: int) -> str:
        if dz == -1: return "N"
        if dz ==  1: return "S"
        if dx == -1: return "W"
        if dx ==  1: return "E"
        raise ValueError("bad delta")

    @staticmethod
    def _opposite(side: str) -> str:
        return {"N":"S","S":"N","W":"E","E":"W"}[side]

    def _branch_seed(self, side: str) -> int:
        """Сид ветви = BLAKE2b(city_seed, side). Всегда от city_seed!"""
        h = hashlib.blake2b(digest_size=8)
        h.update(str(int(self.s.city_seed)).encode("utf-8"))
        h.update(b":")
        h.update(side.encode("utf-8"))
        return int.from_bytes(h.digest(), "little", signed=False)

    def _is_city_origin(self) -> bool:
        return self.s.world_id == "city" and self.s.cx == 0 and self.s.cz == 0

    def _is_branch_origin(self) -> tuple[bool, str]:
        if not str(self.s.world_id).startswith("branch/"):
            return (False, "")
        bid = str(self.s.world_id).split("/", 1)[1]
        return (self.s.cx == 0 and self.s.cz == 0, bid)

    # ---------- детерминированный набор городских шлюзов ----------
    def _city_gateway_sides(self) -> set[str]:
        if self._city_gate_sides is not None:
            return self._city_gate_sides

        br = self._branches_cfg()
        allowed = [k for k, v in br.items() if v and v.get("enabled", False)]
        if not allowed:
            allowed = ["N", "E", "S", "W"]

        # детерминированная "случайность" от city_seed
        h = hashlib.blake2b(digest_size=16)
        h.update(str(int(self.s.city_seed)).encode("utf-8"))
        h.update(b":gateway")
        base = int.from_bytes(h.digest(), "little", signed=False)

        def nxt(x: int) -> int:
            return (1103515245 * x + 12345) & 0x7fffffff

        # присваиваем каждой стороне псевдослучайный балл, зависящий от base
        # (без лямбд с присваиванием)
        scores: dict[str, int] = {}
        x = base
        for s in sorted(allowed):  # сортировка для стабильности независимо от порядка в пресете
            x = nxt(x)
            scores[s] = x

        order = sorted(allowed, key=lambda s: scores[s])

        kmin = 2
        kmax = min(4, len(allowed))
        span = kmax - kmin
        k = kmin if span == 0 else (kmin + (base % (span + 1)))

        self._city_gate_sides = set(order[:k])
        return self._city_gate_sides

    # ---------- IO ----------
    def load_center(self) -> dict:
        k = self.s.key()
        if k in self.s.cache:
            return self.s.cache[k]
        data = generate_or_load(self.s.seed, self.s.cx, self.s.cz,
                                pathlib.Path(self.s.preset_path), self.s.world_id)
        self.s.cache[k] = data
        return data

    def get_neighbor(self, dcx: int, dcz: int) -> dict:
        key = (self.s.cx + dcx, self.s.cz + dcz, int(self.s.seed), str(self.s.world_id), 1)
        if key in self.s.cache:
            return self.s.cache[key]
        data = generate_or_load(int(self.s.seed), self.s.cx + dcx, self.s.cz + dcz,
                                pathlib.Path(self.s.preset_path), self.s.world_id)
        self.s.cache[key] = data
        return data

    # ---------- навигация с учётом gateway ----------
    def _has_port(self, data: dict, side: str) -> bool:
        return bool((data or {}).get("ports", {}).get(side) or [])

    def can_move(self, dx: int, dz: int) -> bool:
        side = self._side_from_delta(dx, dz)
        # 1) из города (0,0) по шлюзу в ветвь
        if self._is_city_origin() and side in self._city_gateway_sides():
            return True
        # 2) из ветви (0,0) по противоположной стороне — назад в город
        is_origin, bid = self._is_branch_origin()
        if is_origin and side == self._opposite(bid):
            return True
        # 3) обычный шов: порты у текущего и у соседа
        center = self.load_center()
        if not self._has_port(center, side):
            return False
        neighbor = self.get_neighbor(dx, dz)
        return self._has_port(neighbor, self._opposite(side))

    def move(self, dx: int, dz: int) -> dict:
        side = self._side_from_delta(dx, dz)

        # переход: город -> ветвь
        if self._is_city_origin() and side in self._city_gateway_sides():
            self.s.world_id = f"branch/{side}"
            self.s.seed = self._branch_seed(side)   # ВАЖНО: от city_seed
            self.s.cx, self.s.cz = 0, 0
            return self.load_center()

        # переход: ветвь -> город (только с (0,0) ветви и через opposite)
        is_origin, bid = self._is_branch_origin()
        if is_origin and side == self._opposite(bid):
            self.s.world_id = "city"
            self.s.seed = int(self.s.city_seed)     # ВОЗВРАТ ИМЕННО ГОРОДСКОГО СИДА
            self.s.cx, self.s.cz = 0, 0
            return self.load_center()

        # обычный сосед
        self.s.cx += dx
        self.s.cz += dz
        return self.load_center()
