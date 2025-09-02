# run_pygame_tester.py
import sys
import pathlib
import pygame
import multiprocessing as mp

# Добавляем корень проекта в пути
ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_engine.game_logic.world import GameWorld
from game_engine.game_logic.generation_worker import worker_main
from pygame_tester.renderer import Renderer, Camera
from pygame_tester.config import SCREEN_WIDTH, SCREEN_HEIGHT, BACKGROUND_COLOR, TILE_SIZE, CHUNK_SIZE


# <<< НАЧАЛО НОВОГО КОДА: Экран для ввода SEED >>>


def get_seed_from_input_screen(screen: pygame.Surface) -> int | None:
    """
    Отображает экран для ввода сида и обрабатывает ввод.
    Возвращает сид в виде числа или None, если пользователь закрыл окно.
    """
    font = pygame.font.Font(None, 50)
    input_box = pygame.Rect(SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT // 2 - 25, 300, 50)
    color_inactive = pygame.Color('lightskyblue3')
    color_active = pygame.Color('dodgerblue2')
    color = color_inactive
    active = False
    text = ''
    clock = pygame.time.Clock()

    prompt_surface = font.render("Enter Seed and Press Enter", True, (255, 255, 255))
    prompt_rect = prompt_surface.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 80))

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None  # Сигнал для выхода из программы
            if event.type == pygame.MOUSEBUTTONDOWN:
                if input_box.collidepoint(event.pos):
                    active = not active
                else:
                    active = False
                color = color_active if active else color_inactive
            if event.type == pygame.KEYDOWN:
                if active:
                    if event.key == pygame.K_RETURN:
                        try:
                            # Если текст пустой, используем сид по умолчанию
                            seed_value = int(text) if text else 123
                            print(f"Seed entered: {seed_value}")
                            return seed_value
                        except ValueError:
                            print(f"Invalid input '{text}', using default seed 123.")
                            return 123
                    elif event.key == pygame.K_BACKSPACE:
                        text = text[:-1]
                    else:
                        # Принимаем только цифры
                        if event.unicode.isdigit():
                            text += event.unicode

        screen.fill(BACKGROUND_COLOR)

        # Отрисовка текста-подсказки
        screen.blit(prompt_surface, prompt_rect)

        # Отрисовка поля для ввода
        txt_surface = font.render(text, True, (255, 255, 255))
        input_box.w = max(300, txt_surface.get_width() + 20)
        input_box.x = SCREEN_WIDTH // 2 - input_box.w // 2  # Центрируем поле

        screen.blit(txt_surface, (input_box.x + 10, input_box.y + 10))
        pygame.draw.rect(screen, color, input_box, 2)

        pygame.display.flip()
        clock.tick(30)


# <<< КОНЕЦ НОВОГО КОДА >>>


def main():
    mp.freeze_support()

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Pygame World Tester")
    clock = pygame.time.Clock()

    # --- ИЗМЕНЕНИЕ: Получаем сид через новый UI, а не через консоль ---
    city_seed = get_seed_from_input_screen(screen)
    if city_seed is None:
        print("Window closed. Exiting.")
        pygame.quit()
        sys.exit()
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

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

    def restart_world(new_seed: int):
        nonlocal task_queue, worker_process, game_world
        # закрыть старый воркер
        try:
            task_queue.put(None)
        except Exception:
            pass
        if worker_process.is_alive():
            worker_process.join(timeout=2)
            if worker_process.is_alive():
                worker_process.terminate()
        # запустить новый воркер и мир
        task_queue = mp.Queue()
        worker_process = mp.Process(target=worker_main, args=(task_queue, new_seed), daemon=True)
        worker_process.start()
        print(f"Restart with seed {new_seed}")
        game_world = GameWorld(new_seed, task_queue)

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                screen_x, screen_y = event.pos
                target_wx = camera.top_left_wx + screen_x // TILE_SIZE
                target_wz = camera.top_left_wz + screen_y // TILE_SIZE
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