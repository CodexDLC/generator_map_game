# ПЕРЕПИШИТЕ ФАЙЛ: run_pygame_tester.py
import sys
import pathlib
import json
import pygame


# --- Настройка путей ---
ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# --- Основные компоненты нашей архитектуры ---
from game_engine.world_actor import WorldActor
from game_engine.core.preset import load_preset
from game_engine.generators._base.generator import BaseGenerator
from game_engine.world_structure.regions import RegionManager
from game_engine.game_logic.world import GameWorld

# --- Компоненты Pygame ---
from pygame_tester.renderer import Renderer, Camera
from pygame_tester.config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    BACKGROUND_COLOR,
    TILE_SIZE,
    CHUNK_SIZE,
    MENU_WIDTH,
    ARTIFACTS_ROOT,
    PRESET_PATH,
    VIEWPORT_HEIGHT_TILES,
    VIEWPORT_WIDTH_TILES,
)
from pygame_tester.ui import SideMenu


def get_seed_from_console() -> int:
    """Запрашивает сид в консоли, пока не будет введено корректное число."""
    while True:
        try:
            seed_str = input(">>> Enter world seed (e.g., 123) and press Enter: ")
            return int(seed_str) if seed_str else 123
        except ValueError:
            print("Invalid input. Please enter a number.")


def main():
    """Главная функция, управляющая всем процессом."""
    print("--- World Generation Initializing ---")
    city_seed = get_seed_from_console()

    preset_data = json.loads(PRESET_PATH.read_text())
    preset = load_preset(preset_data)
    base_generator = BaseGenerator(preset)
    region_manager = RegionManager(city_seed, preset, base_generator, ARTIFACTS_ROOT)
    world_actor = WorldActor(city_seed, preset, ARTIFACTS_ROOT, progress_callback=print)

    # --- ИЗМЕНЕНИЕ: Просто просим "воркера" подготовить стартовую зону ---
    world_actor.prepare_starting_area(region_manager)

    print("\n--- World Generation Complete. Starting Game Client ---")

    # --- (остальная часть функции main остается без изменений) ---
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Pygame World Tester")
    clock = pygame.time.Clock()
    game_world = GameWorld(city_seed)
    renderer = Renderer(screen)
    camera = Camera()
    side_menu = SideMenu(x=0, y=0, width=MENU_WIDTH, height=SCREEN_HEIGHT)
    side_menu.add_button("Toggle Minimap", side_menu.minimap.toggle_visibility)
    viewport_width = VIEWPORT_WIDTH_TILES * TILE_SIZE
    viewport_height = VIEWPORT_HEIGHT_TILES * TILE_SIZE
    game_surface = pygame.Surface((viewport_width, viewport_height))
    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if side_menu.handle_event(event):
                continue
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_x, mouse_y = event.pos
                if mouse_x > MENU_WIDTH:
                    game_surface_x = mouse_x - MENU_WIDTH
                    target_wx = camera.top_left_wx + game_surface_x // TILE_SIZE
                    target_wz = camera.top_left_wz + mouse_y // TILE_SIZE
                    game_world.set_player_target(target_wx, target_wz)
        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]:
            game_world.move_player_by(0, -1)
        if keys[pygame.K_s]:
            game_world.move_player_by(0, 1)
        if keys[pygame.K_a]:
            game_world.move_player_by(-1, 0)
        if keys[pygame.K_d]:
            game_world.move_player_by(1, 0)
        game_world.update(dt)
        state = game_world.get_render_state()
        player_wx, player_wz = state["player_wx"], state["player_wz"]
        camera.center_on_player(player_wx, player_wz)
        screen.fill(BACKGROUND_COLOR)
        renderer.draw_world(camera, state["game_world"], game_surface)
        if state["path"]:
            renderer.draw_path(state["path"], camera, game_surface)
        renderer.draw_player(player_wx, player_wz, camera, game_surface)
        screen.blit(game_surface, (MENU_WIDTH, 0))
        current_cx = player_wx // CHUNK_SIZE
        current_cz = player_wz // CHUNK_SIZE
        side_menu.draw(screen, state["world_manager"], current_cx, current_cz)
        renderer.draw_status(state["world_manager"], player_wx, player_wz)
        pygame.display.flip()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
