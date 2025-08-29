from __future__ import annotations
import json, pathlib, hashlib
from typing import Dict, Set, Tuple
from .state import WorldState
from ...services.worldgen import generate_or_load


class WorldController:
    def __init__(self, state: WorldState):
        self.s = state
        self._branches = None
        self._city_gate_sides: Set[str] | None = None

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
    # <<< НОВЫЙ ВСПОМОГАТЕЛЬНЫЙ МЕТОД >>>
    @staticmethod
    def _delta_from_side(side: str) -> tuple[int, int]:
        """Преобразует сторону ('N', 'E', 'S', 'W') в смещение (dx, dz)."""
        if side == "N": return (0, -1)
        if side == "S": return (0, 1)
        if side == "W": return (-1, 0)
        if side == "E": return (1, 0)
        raise ValueError("bad side")

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

    def _is_branch(self) -> Tuple[bool, str]:
        if not str(self.s.world_id).startswith("branch/"):
            return False, ""
        bid = str(self.s.world_id).split("/", 1)[1]  # 'N'|'E'|'S'|'W'...
        return True, bid

    def _is_branch_origin(self) -> tuple[bool, str]:
        """Проверяет, находится ли игрок на стартовом чанке ветки."""
        if not str(self.s.world_id).startswith("branch/"):
            return (False, "")

        branch_id = str(self.s.world_id).split("/", 1)[1]

        # Стартовые координаты ветки теперь не (0,0), а смещение от города
        origin_dx, origin_dz = self._delta_from_side(branch_id)
        is_at_origin = (self.s.cx == origin_dx and self.s.cz == origin_dz)

        return is_at_origin, branch_id


    # ---------- домены ветвей ----------
    def _branch_domain(self, bid: str) -> dict:
        """Читает domain из пресета для выбранной ветви (если нет — пустой)."""
        br = self._branches_cfg()
        return dict(br.get(bid, {}).get("domain", {})) if bid in br else {}

    @staticmethod
    def _in_domain(cx: int, cz: int, dom: dict) -> bool:
        if "x_min" in dom and cx < int(dom["x_min"]): return False
        if "x_max" in dom and cx > int(dom["x_max"]): return False
        if "z_min" in dom and cz < int(dom["z_min"]): return False
        if "z_max" in dom and cz > int(dom["z_max"]): return False
        return True

    # ---------- детерминированный набор городских шлюзов ----------
    def _city_gateway_sides(self) -> Set[str]:
        if self._city_gate_sides is not None:
            return self._city_gate_sides

        br = self._branches_cfg()
        allowed = [k for k, v in br.items() if v and v.get("enabled", False)]
        if not allowed:
            allowed = ["N", "E", "S", "W"]

        # детерминированная «случайность» от city_seed
        h = hashlib.blake2b(digest_size=16)
        h.update(str(int(self.s.city_seed)).encode("utf-8"))
        h.update(b":gateway")
        base = int.from_bytes(h.digest(), "little", signed=False)

        def nxt(x: int) -> int:
            return (1103515245 * x + 12345) & 0x7fffffff

        scores: dict[str, int] = {}
        x = base
        for s in sorted(allowed):
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

    # ---------- навигация с учётом gateway и домена ----------
    def _has_port(self, data: dict, side: str) -> bool:
        return bool((data or {}).get("ports", {}).get(side) or [])

    def can_move(self, dx: int, dz: int) -> bool:
        side = self._side_from_delta(dx, dz)

        # Город: можно уйти ТОЛЬКО со стартового (0,0) и ТОЛЬКО по шлюзам
        if self.s.world_id == "city":
            return self._is_city_origin() and (side in self._city_gateway_sides())

        # Ветвь: спец-возврат в город с (0,0) через противоположную сторону
        is_origin, bid = self._is_branch_origin()
        if is_origin and side == self._opposite(bid):
            return True

        # Ограничение доменом ветви
        is_b, bid = self._is_branch()
        if is_b:
            dom = self._branch_domain(bid)
            nx, nz = self.s.cx + dx, self.s.cz + dz
            if not self._in_domain(nx, nz, dom):
                return False

        # Обычная проверка портов (обе стороны)
        center = self.load_center()
        if not self._has_port(center, side):
            return False
        neighbor = self.get_neighbor(dx, dz)
        return self._has_port(neighbor, self._opposite(side))

    def move(self, dx: int, dz: int) -> dict:
        side = self._side_from_delta(dx, dz)

        # Переход: город -> ветвь
        if self._is_city_origin() and side in self._city_gateway_sides():
            self.s.world_id = f"branch/{side}"
            self.s.seed = self._branch_seed(side)
            # Координаты теперь глобальные, а не сбрасываются в (0,0)
            self.s.cx, self.s.cz = dx, dz
            return self.load_center()

        # Переход: ветвь -> город
        is_at_origin, branch_id = self._is_branch_origin()
        # Возврат возможен только со стартового чанка ветки и в сторону города
        if is_at_origin and side == self._opposite(branch_id):
            self.s.world_id = "city"
            self.s.seed = int(self.s.city_seed)
            self.s.cx, self.s.cz = 0, 0 # Возвращаемся в центр города
            return self.load_center()

        # Обычное перемещение по соседним чанкам
        self.s.cx += dx
        self.s.cz += dz
        return self.load_center()
