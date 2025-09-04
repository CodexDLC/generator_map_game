# ОБНОВИТЕ ФАЙЛ: game_engine/game_logic/transition_manager.py
from __future__ import annotations
from typing import Tuple, TYPE_CHECKING

from pygame_tester.config import CHUNK_SIZE
from ..core.constants import KIND_GROUND

if TYPE_CHECKING:
    from .world import GameWorld


class WorldTransitionManager:
    def __init__(self, world_manager):
        self.world_manager = world_manager

    def check_and_trigger_transition(self, wx: int, wz: int, game_world: 'GameWorld') -> Tuple[int, int] | None:
        # --- ИЗМЕНЕНИЕ: УДАЛЯЕМ НЕНУЖНУЮ ПРОВЕРКУ ---
        # if not game_world.pre_generation_complete:
        #     return None
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

        if self.world_manager.world_id != "city":
            return None

        current_cx = wx // CHUNK_SIZE
        current_cz = wz // CHUNK_SIZE
        if current_cx != 0 or current_cz != 0:
            return None

        lx = wx % CHUNK_SIZE
        lz = wz % CHUNK_SIZE
        side = None

        if lx == CHUNK_SIZE - 1: side = "E"
        elif lx == 0: side = "W"
        elif lz == CHUNK_SIZE - 1: side = "S"
        elif lz == 0: side = "N"

        if side:
            chunk_data = self.world_manager.get_chunk_data(0, 0)
            if not chunk_data: return None

            if chunk_data["kind"][lz][lx] == KIND_GROUND:
                print(f"--- Leaving city, entering world_location via gateway: {side} ---")
                self.world_manager.world_id = "world_location"
                self.world_manager.cache.clear()

                if side == "N": new_cx, new_cz = 0, -1
                elif side == "S": new_cx, new_cz = 0, 1
                elif side == "W": new_cx, new_cz = -1, 0
                else: new_cx, new_cz = 1, 0

                # Эта логика была в WorldManager, но ее лучше оставить здесь
                # self.world_manager.player_chunk_cx = new_cx
                # self.world_manager.player_chunk_cz = new_cz
                new_wx = new_cx * CHUNK_SIZE + (CHUNK_SIZE - 1 - lx)
                new_wz = new_cz * CHUNK_SIZE + (CHUNK_SIZE - 1 - lz)
                return (new_wx, new_wz)
        return None