# run_pygame_tester.py
import sys
import pathlib
import pygame
import threading  # <--- ДОБАВЛЯЕМ ИМПОРТ ДЛЯ МНОГОПОТОЧНОСТИ

# Добавляем корень проекта в пути
ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from generator_tester.world_manager import WorldManager
from generator_tester.renderer import Renderer, Camera
from generator_tester.config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, BACKGROUND_COLOR, TILE_SIZE,
    PLAYER_MOVE_SPEED, CHUNK_SIZE
)
from engine.worldgen_core.pathfinding_ai.a_star import find_path


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Pygame World Tester")
    clock = pygame.time.Clock()

    try:
        city_seed_str = input("Enter city seed (default 123): ")
        city_seed = int(city_seed_str) if city_seed_str.strip() else 123
    except ValueError:
        print("Invalid seed, using 123.")
        city_seed = 123

    world_manager = WorldManager(city_seed)
    renderer = Renderer(screen)
    camera = Camera()

    player_wx, player_wz = CHUNK_SIZE // 2, CHUNK_SIZE // 2
    path = []
    move_timer = 0.0

    # ---> ИЗМЕНЕНИЕ 1: Переменная для фонового потока <---
    preload_thread = None

    # ---> ИЗМЕНЕНИЕ 2: Стартовая загрузка <---
    # Сначала синхронно грузим ТОЛЬКО ОДИН стартовый чанк, чтобы игра началась мгновенно
    print("Loading initial chunk (0, 0)...")
    world_manager.get_chunk_data(0, 0)
    world_manager.player_chunk_cx, world_manager.player_chunk_cz = 0, 0
    # Теперь запускаем предзагрузку соседей в ФОНОВОМ потоке
    print("Starting background preload for neighbors...")
    preload_thread = threading.Thread(target=world_manager.preload_chunks_around, args=(0, 0), daemon=True)
    preload_thread.start()

    running = True
    while running:
        # --- Обработка событий (без изменений) ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    screen_x, screen_y = event.pos
                    target_wx = camera.top_left_wx + screen_x // TILE_SIZE
                    target_wz = camera.top_left_wz + screen_y // TILE_SIZE
                    player_cx, player_cz = player_wx // CHUNK_SIZE, player_wz // CHUNK_SIZE
                    target_cx, target_cz = target_wx // CHUNK_SIZE, target_wz // CHUNK_SIZE
                    start_lx, start_lz = player_wx % CHUNK_SIZE, player_wz % CHUNK_SIZE
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

                    chunk_data = world_manager.get_chunk_data(player_cx, player_cz)
                    if chunk_data:
                        local_path = find_path(
                            chunk_data['kind'], chunk_data['height'],
                            (start_lx, start_lz), (end_lx, end_lz)
                        )
                        if local_path:
                            wx_offset = player_cx * CHUNK_SIZE
                            wz_offset = player_cz * CHUNK_SIZE
                            path = [(lx + wx_offset, lz + wz_offset) for lx, lz in local_path]
                            if path: path.pop(0)
                        else:
                            print("Path not found!")

        # --- Ручное управление (без изменений) ---
        keys = pygame.key.get_pressed()
        moved_manually = False
        if keys[pygame.K_w]: player_wz -= 1; moved_manually = True
        if keys[pygame.K_s]: player_wz += 1; moved_manually = True
        if keys[pygame.K_a]: player_wx -= 1; moved_manually = True
        if keys[pygame.K_d]: player_wx += 1; moved_manually = True
        if moved_manually: path = []

        # --- Движение по пути (без изменений) ---
        if path:
            move_timer += clock.get_rawtime() / 1000.0
            if move_timer >= PLAYER_MOVE_SPEED:
                move_timer = 0
                next_pos = path.pop(0)
                player_wx, player_wz = next_pos

        # --- Переход между мирами (без изменений) ---
        transition_result = world_manager.check_and_trigger_transition(player_wx, player_wz)
        if transition_result:
            player_wx, player_wz = transition_result
            path = []
            new_cx, new_cz = player_wx // CHUNK_SIZE, player_wz // CHUNK_SIZE
            world_manager.preload_chunks_around(new_cx, new_cz)

        # --- Обновление камеры и фоновая предзагрузка ---
        camera.center_on_player(player_wx, player_wz)
        current_cx, current_cz = player_wx // CHUNK_SIZE, player_wz // CHUNK_SIZE
        if (current_cx, current_cz) != (world_manager.player_chunk_cx, world_manager.player_chunk_cz):
            print(f"Player moved to new chunk: ({current_cx}, {current_cz})")
            world_manager.player_chunk_cx, world_manager.player_chunk_cz = current_cx, current_cz

            # ---> ИЗМЕНЕНИЕ 3: Запускаем новую предзагрузку в фоне <---
            if preload_thread is None or not preload_thread.is_alive():
                print(f"Starting background preload around ({current_cx}, {current_cz})...")
                preload_thread = threading.Thread(target=world_manager.preload_chunks_around,
                                                  args=(current_cx, current_cz), daemon=True)
                preload_thread.start()
            else:
                print("Note: Previous background preload is still running.")

        # --- Отрисовка (без изменений) ---
        screen.fill(BACKGROUND_COLOR)
        renderer.draw_world(camera, world_manager)
        if path:
            renderer.draw_path(path, camera)
        renderer.draw_player(player_wx, player_wz, camera)
        renderer.draw_status(world_manager, player_wx, player_wz)
        renderer.draw_minimap(world_manager, current_cx, current_cz)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()