# game_engine/game_logic/world.py
from typing import Dict, Any, Tuple, Optional
from multiprocessing import Queue
from enum import Enum, auto

# --- ИЗМЕНЕНИЯ: Все импорты обновлены ---
from .player import Player
from pygame_tester.world_manager import WorldManager
from ..algorithms.pathfinding.a_star import find_path
from pygame_tester.config import CHUNK_SIZE, PLAYER_MOVE_SPEED


class LoadingState(Enum):
    IDLE = auto()
    WAITING_FOR_PRIMARY_CHUNK = auto()
    PRE_GENERATING = auto()


class GameWorld:
    def __init__(self, city_seed: int, task_queue: Queue):
        self.world_manager = WorldManager(city_seed)
        self.task_queue = task_queue
        self.player = Player(wx=CHUNK_SIZE // 2, wz=CHUNK_SIZE // 2)

        self.render_grid_radius = 1
        self.render_grid: Dict[Tuple[int, int], Dict] = {}
        self.last_player_chunk_pos = (-999, -999)
        self.pending_chunks = set()

        self.loading_state = LoadingState.IDLE
        self.pre_generation_complete = False
        self.chunks_to_pre_generate: set[Tuple[int, int]] = set()

        self.primary_chunk_to_load: Optional[Tuple[int, int]] = None

        self._load_and_render_chunk_at((0, 0))
        self.start_pre_generation()

    def start_pre_generation(self):
        """Запускает предгенерацию стартовой зоны 3x3."""
        print("[Pre-Gen] Starting pre-generation of the 3x3 starting area...")
        self.loading_state = LoadingState.PRE_GENERATING

        coords_to_check = [
            (cx, cz) for cx in range(-1, 2) for cz in range(-1, 2)
        ]

        for cx, cz in coords_to_check:
            chunk_path = self.world_manager._get_chunk_path("world_location", self.world_manager.current_seed, cx, cz)
            if not (chunk_path / "chunk.rle.json").exists():
                self.chunks_to_pre_generate.add((cx, cz))

        if not self.chunks_to_pre_generate:
            print("[Pre-Gen] -> All chunks already exist. Pre-generation is complete.")
            self.pre_generation_complete = True
            self.loading_state = LoadingState.IDLE
        else:
            print(f"[Pre-Gen] -> Need to generate {len(self.chunks_to_pre_generate)} chunks. Queuing tasks...")
            for cx, cz in self.chunks_to_pre_generate:
                task = ("world_location", self.world_manager.current_seed, cx, cz)
                self.task_queue.put(task)

    def _check_pre_generation_status(self):
        """Проверяет, не завершил ли воркер генерацию недостающих чанков."""
        if not self.chunks_to_pre_generate:
            return

        remaining_chunks = self.chunks_to_pre_generate.copy()
        for cx, cz in remaining_chunks:
            chunk_path = self.world_manager._get_chunk_path("world_location", self.world_manager.current_seed, cx, cz)
            if (chunk_path / "chunk.rle.json").exists():
                self.chunks_to_pre_generate.remove((cx, cz))
                print(f"[Pre-Gen] -> Chunk ({cx},{cz}) is ready. Remaining: {len(self.chunks_to_pre_generate)}")

        if not self.chunks_to_pre_generate:
            print("[Pre-Gen] -> All chunks generated. Pre-generation complete!")
            self.pre_generation_complete = True
            self.loading_state = LoadingState.IDLE

    def update(self, dt: float):
        if self.loading_state == LoadingState.PRE_GENERATING:
            self._check_pre_generation_status()
            return

        player_cx = self.player.wx // CHUNK_SIZE
        player_cz = self.player.wz // CHUNK_SIZE

        if self.world_manager.world_id != "city" or self.pre_generation_complete:
            grid_needs_update = ((player_cx, player_cz) != self.last_player_chunk_pos or self.pending_chunks)
            if grid_needs_update:
                self.last_player_chunk_pos = (player_cx, player_cz)
                self._update_surrounding_grid(player_cx, player_cz)

        self._handle_path_movement(dt)
        self._check_world_transition()

    def _update_surrounding_grid(self, center_cx: int, center_cz: int):
        """Поддерживает сетку чанков вокруг игрока."""
        if self.world_manager.world_id == "city":
            self._load_and_render_chunk_at((0, 0))
            return

        needed_chunks = set()
        for dz in range(-self.render_grid_radius, self.render_grid_radius + 1):
            for dx in range(-self.render_grid_radius, self.render_grid_radius + 1):
                pos = (center_cx + dx, center_cz + dz)
                needed_chunks.add(pos)

        current_chunks_pos = set(self.render_grid.keys())
        for pos in current_chunks_pos - needed_chunks:
            del self.render_grid[pos]
        self.pending_chunks -= (current_chunks_pos - needed_chunks)

        for pos in needed_chunks:
            self._load_and_render_chunk_at(pos)

    def _load_and_render_chunk_at(self, pos: Tuple[int, int]):
        """Загружает чанк или запрашивает его генерацию."""
        if pos in self.render_grid:
            return

        chunk_data = self.world_manager.get_chunk_data(pos[0], pos[1])

        if chunk_data:
            self.render_grid[pos] = chunk_data
            self.pending_chunks.discard(pos)
        elif pos not in self.pending_chunks:
            if self.world_manager.world_id != "city":
                print(f"Chunk {pos} not found. Queueing for generation.")
                task = (self.world_manager.world_id, self.world_manager.current_seed, pos[0], pos[1])
                self.task_queue.put(task)
                self.pending_chunks.add(pos)

    def _try_to_load_primary_chunk(self):
        if self.primary_chunk_to_load is None:
            self.loading_state = LoadingState.IDLE
            return

        cx, cz = self.primary_chunk_to_load
        chunk_data = self.world_manager.get_chunk_data(cx, cz)

        if chunk_data:
            print(f"Primary chunk ({cx}, {cz}) loaded successfully!")
            self.render_grid[(cx, cz)] = chunk_data
            self.pending_chunks.discard((cx, cz))
            self.primary_chunk_to_load = None
            self.loading_state = LoadingState.IDLE
            self._update_surrounding_grid(cx, cz)

    def _check_world_transition(self):
        """Проверяет и выполняет переход между мирами."""
        transition_result = self.world_manager.transition_manager.check_and_trigger_transition(
            self.player.wx, self.player.wz, self
        )
        if transition_result:
            self.player.wx, self.player.wz = transition_result
            self.player.path = []
            self.render_grid.clear()
            self.pending_chunks.clear()
            new_cx = self.player.wx // CHUNK_SIZE
            new_cz = self.player.wz // CHUNK_SIZE
            self.primary_chunk_to_load = (new_cx, new_cz)
            self.loading_state = LoadingState.WAITING_FOR_PRIMARY_CHUNK
            self._load_and_render_chunk_at(self.primary_chunk_to_load)
            print(f"Transition triggered. New primary target: {self.primary_chunk_to_load}")

    def get_tile_at(self, wx: int, wz: int) -> Dict:
        cx, cz = wx // CHUNK_SIZE, wz // CHUNK_SIZE
        if (cx, cz) not in self.render_grid:
            return {"kind": "void", "height": 0}
        chunk_data = self.render_grid[(cx, cz)]
        lx, lz = wx % CHUNK_SIZE, wz % CHUNK_SIZE
        kind_grid = chunk_data.get("kind", [])
        height_grid = chunk_data.get("height", [])
        is_in_bounds = (0 <= lz < len(kind_grid) and 0 <= lx < len(kind_grid[0]))
        if not is_in_bounds:
            return {"kind": "void", "height": 0}
        kind = kind_grid[lz][lx]
        height = height_grid[lz][lx] if (0 <= lz < len(height_grid) and 0 <= lx < len(height_grid[0])) else 0
        return {"kind": kind, "height": height}

    def set_player_target(self, target_wx: int, target_wz: int):
        player_cx, player_cz = self.player.wx // CHUNK_SIZE, self.player.wz // CHUNK_SIZE
        if (player_cx, player_cz) not in self.render_grid:
            self._update_surrounding_grid(player_cx, player_cz)
        chunk_data = self.render_grid.get((player_cx, player_cz))
        if chunk_data:
            target_cx, target_cz = target_wx // CHUNK_SIZE, target_wz // CHUNK_SIZE
            start_lx, start_lz = self.player.wx % CHUNK_SIZE, self.player.wz % CHUNK_SIZE
            if (player_cx, player_cz) == (target_cx, target_cz):
                end_lx, end_lz = target_wx % CHUNK_SIZE, target_wz % CHUNK_SIZE
            else:
                dx = target_cx - player_cx
                dz = target_cz - player_cz
                if abs(dx) > abs(dz):
                    end_lx = CHUNK_SIZE - 1 if dx > 0 else 0
                    end_lz = target_wz % CHUNK_SIZE
                else:
                    end_lz = CHUNK_SIZE - 1 if dz > 0 else 0
                    end_lx = target_wx % CHUNK_SIZE
            local_path = find_path(
                chunk_data.get('kind', []), chunk_data.get('height', []),
                (start_lx, start_lz), (end_lx, end_lz)
            )
            if local_path:
                wx_offset = player_cx * CHUNK_SIZE
                wz_offset = player_cz * CHUNK_SIZE
                self.player.path = [(lx + wx_offset, lz + wz_offset) for lx, lz in local_path]
                if self.player.path: self.player.path.pop(0)
            else:
                self.player.path = []
                print("Path not found!")

    def move_player_by(self, dx: int, dz: int):
        self.player.wx += dx
        self.player.wz += dz
        self.player.path = []

    def get_render_state(self) -> Dict[str, Any]:
        return {
            "player_wx": self.player.wx, "player_wz": self.player.wz,
            "path": self.player.path, "world_manager": self.world_manager,
            "game_world": self,
        }

    def _handle_path_movement(self, dt: float):
        if not self.player.path: return
        self.player.move_timer += dt
        if self.player.move_timer >= PLAYER_MOVE_SPEED:
            self.player.move_timer = 0
            next_pos = self.player.path.pop(0)
            self.player.wx, self.player.wz = next_pos