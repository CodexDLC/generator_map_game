from typing import Dict, Any, Tuple
from multiprocessing import Queue
import numpy as np

from game_logic.player import Player
from generator_tester.world_manager import WorldManager
from engine.worldgen_core.pathfinding_ai.a_star import find_path
from generator_tester.config import CHUNK_SIZE, PLAYER_MOVE_SPEED


class GameWorld:
    def __init__(self, city_seed: int, task_queue: Queue):
        self.world_manager = WorldManager(city_seed)
        self.task_queue = task_queue
        self.player = Player(wx=CHUNK_SIZE // 2, wz=CHUNK_SIZE // 2)

        self.render_grid_radius = 1
        self.render_grid: Dict[Tuple[int, int], Dict] = {}
        self.last_player_chunk_pos = (-999, -999)

        # Начальная загрузка только города
        self.world_manager.get_chunk_data(0, 0)

    def update(self, dt: float):
        """Главный метод обновления с постоянной проверкой готовности чанков."""
        player_cx = self.player.wx // CHUNK_SIZE
        player_cz = self.player.wz // CHUNK_SIZE

        # --- НОВАЯ ЛОГИКА ОБНОВЛЕНИЯ ---
        grid_needs_update = False
        # 1. Обновляем, если игрок перешел в новый чанк
        if (player_cx, player_cz) != self.last_player_chunk_pos:
            grid_needs_update = True
            self.last_player_chunk_pos = (player_cx, player_cz)

        # 2. Обновляем, если сетка не заполнена (ждем генерацию от воркера)
        expected_chunk_count = (self.render_grid_radius * 2 + 1) ** 2
        if len(self.render_grid) < expected_chunk_count:
            grid_needs_update = True

        if grid_needs_update:
            self._update_render_grid(player_cx, player_cz)
        # --- КОНЕЦ НОВОЙ ЛОГИКИ ---

        self._handle_path_movement(dt)
        self._check_world_transition()

    def _update_render_grid(self, center_cx: int, center_cz: int):
        print(f"Updating render grid around ({center_cx}, {center_cz})...")
        needed_chunks = set()
        for dz in range(-self.render_grid_radius, self.render_grid_radius + 1):
            for dx in range(-self.render_grid_radius, self.render_grid_radius + 1):
                needed_chunks.add((center_cx + dx, center_cz + dz))

        current_chunks = set(self.render_grid.keys())
        for pos in current_chunks - needed_chunks:
            del self.render_grid[pos]

        for pos in needed_chunks:
            if pos not in self.render_grid:
                chunk_data = self.world_manager.get_chunk_data(pos[0], pos[1])
                if chunk_data:
                    self.render_grid[pos] = chunk_data

    def get_tile_at(self, wx: int, wz: int) -> Dict:
        cx, cz = wx // CHUNK_SIZE, wz // CHUNK_SIZE
        if (cx, cz) not in self.render_grid:
            return {"kind": "void"}

        chunk_data = self.render_grid[(cx, cz)]
        lx, lz = wx % CHUNK_SIZE, wz % CHUNK_SIZE

        kind_grid = chunk_data.get("kind", [])
        if not (0 <= lz < len(kind_grid) and 0 <= lx < len(kind_grid[0])):
            return {"kind": "void"}

        return {"kind": kind_grid[lz][lx]}

    def set_player_target(self, target_wx: int, target_wz: int):
        player_cx, player_cz = self.player.wx // CHUNK_SIZE, self.player.wz // CHUNK_SIZE
        target_cx, target_cz = target_wx // CHUNK_SIZE, target_wz // CHUNK_SIZE

        start_lx, start_lz = self.player.wx % CHUNK_SIZE, self.player.wz % CHUNK_SIZE
        end_lx, end_lz = target_wx % CHUNK_SIZE, target_wz % CHUNK_SIZE

        if (player_cx, player_cz) != (target_cx, target_cz):
            dx = target_cx - player_cx
            dz = target_cz - player_cz
            if abs(dx) > abs(dz):
                end_lz = target_wz % CHUNK_SIZE
                end_lx = CHUNK_SIZE - 1 if dx > 0 else 0
            else:
                end_lx = target_wx % CHUNK_SIZE
                end_lz = CHUNK_SIZE - 1 if dz > 0 else 0

        if (player_cx, player_cz) not in self.render_grid:
            self._update_render_grid(player_cx, player_cz)

        chunk_data = self.render_grid.get((player_cx, player_cz))
        if chunk_data:
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

    def _check_world_transition(self):
        """Проверяет переход Город -> Ветка и просто ставит задачи в очередь."""
        transition_result = self.world_manager.check_and_trigger_transition(self.player.wx, self.player.wz)
        if transition_result:
            self.player.wx, self.player.wz = transition_result
            self.player.path = []

            new_cx, new_cz = self.player.wx // CHUNK_SIZE, self.player.wz // CHUNK_SIZE

            # Просто очищаем все и ставим задачи в очередь.
            # Новый update() сам подхватит сгенерированные чанки.
            self.render_grid.clear()
            self.last_player_chunk_pos = (-999, -999)  # Форсируем обновление на следующем кадре
            self._queue_preload_tasks_at(new_cx, new_cz)

    def _queue_preload_tasks_at(self, cx: int, cz: int):
        tasks = self.world_manager.get_chunks_for_preloading(cx, cz)
        if tasks:
            print(f"Queueing {len(tasks)} new chunks for generation.")
            for task in tasks:
                self.task_queue.put(task)