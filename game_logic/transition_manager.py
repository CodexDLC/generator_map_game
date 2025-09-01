# game_logic/transition_manager.py
from typing import Tuple
from generator_tester.config import CHUNK_SIZE
from engine.worldgen_core.base.constants import KIND_GROUND


class WorldTransitionManager:
    def __init__(self, world_manager):
        self.world_manager = world_manager

    def check_and_trigger_transition(self, wx: int, wz: int) -> Tuple[int, int] | None:
        """
        Проверяет, не находится ли игрок на границе мира (например, города),
        и инициирует переход в новый мир (ветку), если это необходимо.
        """
        if self.world_manager.world_id != "city":
            return None

        lx = wx % CHUNK_SIZE
        lz = wz % CHUNK_SIZE
        side = None


        # Определяем, на какой границе находится игрок
        if wx == CHUNK_SIZE - 1 and (0 <= wz < CHUNK_SIZE):
            side = "E"
        elif wx == 0 and (0 <= wz < CHUNK_SIZE):
            side = "W"
        elif wz == CHUNK_SIZE - 1 and (0 <= wx < CHUNK_SIZE):
            side = "S"
        elif wz == 0 and (0 <= wx < CHUNK_SIZE):
            side = "N"

        if side:
            # Проверяем, что тайл на границе - это проходимая земля
            chunk_data = self.world_manager.get_chunk_data(0, 0)
            kind = chunk_data["kind"]
            h = len(kind);
            w = len(kind[0]) if h else 0
            if not (0 <= lz < h and 0 <= lx < w):
                return None
            if chunk_data and chunk_data["kind"][lz][lx] == KIND_GROUND:
                print(f"--- Entering Gateway to Branch: {side} ---")

                # Обновляем состояние WorldManager для нового мира
                self.world_manager.world_id = f"branch/{side}"
                self.world_manager.current_seed = self.world_manager._branch_seed(side)
                self.world_manager.cache.clear()

                # Рассчитываем новые координаты чанка и игрока
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

                # Помещаем игрока у противоположной границы нового чанка
                new_wx = new_cx * CHUNK_SIZE + (CHUNK_SIZE - 1 - lx)
                new_wz = new_cz * CHUNK_SIZE + (CHUNK_SIZE - 1 - lz)

                return (new_wx, new_wz)

        return None