# game_logic/transition_manager.py
from typing import Tuple, TYPE_CHECKING
from generator_tester.config import CHUNK_SIZE
from engine.worldgen_core.base.constants import KIND_GROUND

if TYPE_CHECKING:
    from .world import GameWorld


class WorldTransitionManager:
    def __init__(self, world_manager):
        self.world_manager = world_manager

    def check_and_trigger_transition(self, wx: int, wz: int, game_world: "GameWorld") -> Tuple[int, int] | None:
        """
        Проверяет переход из города, но только если предгенерация завершена.
        """
        # <<< НОВОЕ УСЛОВИЕ БЛОКИРОВКИ >>>
        if not game_world.pre_generation_complete:
            # Если предгенерация не завершена, выходы из города закрыты
            return None

        if self.world_manager.world_id != "city":
            return None

        # ... (остальная логика метода без изменений) ...

        current_cx = wx // CHUNK_SIZE
        current_cz = wz // CHUNK_SIZE
        if current_cx != 0 or current_cz != 0:
            return None

        lx = wx % CHUNK_SIZE
        lz = wz % CHUNK_SIZE
        side = None

        if lx == CHUNK_SIZE - 1:
            side = "E"
        elif lx == 0:
            side = "W"
        elif lz == CHUNK_SIZE - 1:
            side = "S"
        elif lz == 0:
            side = "N"

        if side:
            chunk_data = self.world_manager.get_chunk_data(0, 0)
            if not chunk_data: return None

            if chunk_data["kind"][lz][lx] == KIND_GROUND:
                print(f"--- Leaving city, entering world_location via gateway: {side} ---")

                self.world_manager.world_id = "world_location"
                self.world_manager.cache.clear()

                if side == "N":
                    new_cx, new_cz = 0, -1
                elif side == "S":
                    new_cx, new_cz = 0, 1
                elif side == "W":
                    new_cx, new_cz = -1, 0
                else:
                    new_cx, new_cz = 1, 0

                self.world_manager.player_chunk_cx = new_cx
                self.world_manager.player_chunk_cz = new_cz

                new_wx = new_cx * CHUNK_SIZE + (CHUNK_SIZE - 1 - lx)
                new_wz = new_cz * CHUNK_SIZE + (CHUNK_SIZE - 1 - lz)

                return (new_wx, new_wz)

        return None