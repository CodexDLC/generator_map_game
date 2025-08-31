# run_pygame_tester.py
import sys
import pathlib
import pygame
import multiprocessing as mp

# Добавляем корень проекта в пути
ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_logic.world import GameWorld
from game_logic.generation_worker import worker_main
from generator_tester.renderer import Renderer, Camera
from generator_tester.config import SCREEN_WIDTH, SCREEN_HEIGHT, BACKGROUND_COLOR, TILE_SIZE, CHUNK_SIZE


def main():
    mp.freeze_support()

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

    task_queue = mp.Queue()
    worker_process = mp.Process(
        target=worker_main,
        args=(task_queue, city_seed),
        daemon=True
    )
    worker_process.start()

    print("Initializing Game World...")
    game_world = GameWorld(city_seed, task_queue)

    renderer = Renderer(screen)
    camera = Camera()

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                screen_x, screen_y = event.pos
                target_wx = camera.top_left_wx + screen_x // TILE_SIZE

                # <<< =============== ВОТ ЗДЕСЬ БЫЛА ОШИБКА =============== >>>
                # Было: target_wz = camera.top_left_wx + screen_y // TILE_SIZE
                # Стало:
                target_wz = camera.top_left_wz + screen_y // TILE_SIZE
                # <<< ===================================================== >>>

                game_world.set_player_target(target_wx, target_wz)

        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]: game_world.move_player_by(0, -1)
        if keys[pygame.K_s]: game_world.move_player_by(0, 1)
        if keys[pygame.K_a]: game_world.move_player_by(-1, 0)
        if keys[pygame.K_d]: game_world.move_player_by(1, 0)

        game_world.update(dt)

        state = game_world.get_render_state()
        player_wx = state["player_wx"]
        player_wz = state["player_wz"]

        camera.center_on_player(player_wx, player_wz)

        screen.fill(BACKGROUND_COLOR)

        renderer.draw_world(camera, state["game_world"])

        if state["path"]:
            renderer.draw_path(state["path"], camera)

        renderer.draw_player(player_wx, player_wz, camera)
        renderer.draw_status(state["world_manager"], player_wx, player_wz)

        current_cx = player_wx // CHUNK_SIZE
        current_cz = player_wz // CHUNK_SIZE
        renderer.draw_minimap(state["world_manager"], current_cx, current_cz)

        pygame.display.flip()

    print("Main loop finished. Shutting down worker...")
    task_queue.put(None)
    worker_process.join(timeout=5)
    if worker_process.is_alive():
        print("Worker did not shut down gracefully. Terminating.")
        worker_process.terminate()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()