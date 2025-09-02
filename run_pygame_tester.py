# run_pygame_tester.py
import sys
import pathlib
import pygame
import multiprocessing as mp

ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_engine.game_logic.world import GameWorld
from game_engine.game_logic.generation_worker import worker_main
from pygame_tester.renderer import Renderer, Camera
# --- НАЧАЛО ИЗМЕНЕНИЯ: Импортируем новые константы ---
from pygame_tester.config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, BACKGROUND_COLOR, TILE_SIZE, CHUNK_SIZE,
    MENU_WIDTH, VIEWPORT_WIDTH_TILES, VIEWPORT_HEIGHT_TILES
)
# --- КОНЕЦ ИЗМЕНЕНИЯ ---
from pygame_tester.ui import SideMenu


def get_seed_from_input_screen(screen: pygame.Surface) -> int | None:
    # ... (содержимое этой функции остается без изменений) ...
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
    restart_prompt_font = pygame.font.Font(None, 32)
    restart_prompt_surface = restart_prompt_font.render("Press 'R' in-game to restart with a new seed", True,
                                                        (180, 180, 180))
    restart_prompt_rect = restart_prompt_surface.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 40))
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: return None
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
                            return int(text) if text else 123
                        except ValueError:
                            return 123
                    elif event.key == pygame.K_BACKSPACE:
                        text = text[:-1]
                    else:
                        if event.unicode.isdigit(): text += event.unicode
        screen.fill(BACKGROUND_COLOR)
        screen.blit(prompt_surface, prompt_rect)
        screen.blit(restart_prompt_surface, restart_prompt_rect)
        txt_surface = font.render(text, True, (255, 255, 255))
        input_box.w = max(300, txt_surface.get_width() + 20)
        input_box.x = SCREEN_WIDTH // 2 - input_box.w // 2
        screen.blit(txt_surface, (input_box.x + 10, input_box.y + 10))
        pygame.draw.rect(screen, color, input_box, 2)
        pygame.display.flip()
        clock.tick(30)


def main():
    mp.freeze_support()
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Pygame World Tester")
    clock = pygame.time.Clock()

    # --- НАЧАЛО ИЗМЕНЕНИЯ: Создаем отдельную поверхность для игрового мира ---
    viewport_width = VIEWPORT_WIDTH_TILES * TILE_SIZE
    viewport_height = VIEWPORT_HEIGHT_TILES * TILE_SIZE
    game_surface = pygame.Surface((viewport_width, viewport_height))
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    city_seed = get_seed_from_input_screen(screen)
    if city_seed is None:
        pygame.quit();
        sys.exit()

    task_queue = mp.Queue()
    worker_process = mp.Process(target=worker_main, args=(task_queue, city_seed), daemon=True)
    worker_process.start()
    game_world = GameWorld(city_seed, task_queue)
    renderer = Renderer(screen)
    camera = Camera()

    def restart_world(new_seed: int):
        nonlocal task_queue, worker_process, game_world
        try:
            task_queue.put(None)
        except Exception:
            pass
        if worker_process.is_alive():
            worker_process.join(timeout=2)
            if worker_process.is_alive(): worker_process.terminate()
        task_queue = mp.Queue()
        worker_process = mp.Process(target=worker_main, args=(task_queue, new_seed), daemon=True)
        worker_process.start()
        game_world = GameWorld(new_seed, task_queue)

    running = True

    def trigger_restart():
        nonlocal city_seed, running
        new_seed = get_seed_from_input_screen(screen)
        if new_seed is None:
            running = False
        else:
            city_seed = new_seed
            restart_world(city_seed)

    side_menu = SideMenu(x=0, y=0, width=MENU_WIDTH, height=SCREEN_HEIGHT)
    side_menu.add_button("Restart (R)", trigger_restart)
    # --- НАЧАЛО ИЗМЕНЕНИЯ: Добавляем кнопку для миникарты ---
    side_menu.add_button("Toggle Minimap", side_menu.minimap.toggle_visibility)
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    while running:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            if side_menu.handle_event(event): continue
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                trigger_restart()
                continue
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # --- НАЧАЛО ИЗМЕНЕНИЯ: Корректируем координаты клика ---
                mouse_x, mouse_y = event.pos
                if mouse_x > MENU_WIDTH:  # Клик в игровой зоне
                    # Пересчитываем координаты относительно game_surface
                    game_surface_x = mouse_x - MENU_WIDTH
                    target_wx = camera.top_left_wx + game_surface_x // TILE_SIZE
                    target_wz = camera.top_left_wz + mouse_y // TILE_SIZE
                    game_world.set_player_target(target_wx, target_wz)
                # --- КОНЕЦ ИЗМЕНЕНИЯ ---

        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]: game_world.move_player_by(0, -1)
        if keys[pygame.K_s]: game_world.move_player_by(0, 1)
        if keys[pygame.K_a]: game_world.move_player_by(-1, 0)
        if keys[pygame.K_d]: game_world.move_player_by(1, 0)

        game_world.update(dt)
        state = game_world.get_render_state()
        player_wx, player_wz = state["player_wx"], state["player_wz"]
        camera.center_on_player(player_wx, player_wz)

        # --- НАЧАЛО ИЗМЕНЕНИЯ: Логика отрисовки ---
        # 1. Очищаем главный экран
        screen.fill(BACKGROUND_COLOR)

        # 2. Рисуем игровой мир на его отдельной поверхности
        renderer.draw_world(camera, state["game_world"], game_surface)
        if state["path"]:
            renderer.draw_path(state["path"], camera, game_surface)
        renderer.draw_player(player_wx, player_wz, camera, game_surface)

        # 3. "Приклеиваем" игровую поверхность к основному экрану со смещением
        screen.blit(game_surface, (MENU_WIDTH, 0))

        # 4. Рисуем UI (меню и статус-бар) поверх всего
        current_cx = player_wx // CHUNK_SIZE
        current_cz = player_wz // CHUNK_SIZE
        side_menu.draw(screen, state["world_manager"], current_cx, current_cz)
        renderer.draw_status(state["world_manager"], player_wx, player_wz)
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

        pygame.display.flip()

    task_queue.put(None)
    if worker_process.is_alive():
        worker_process.join(timeout=5)
        if worker_process.is_alive(): worker_process.terminate()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()