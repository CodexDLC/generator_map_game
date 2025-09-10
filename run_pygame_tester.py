# Файл: run_pygame_tester.py
import sys
import json
# --- ИЗМЕНЕНИЕ: Убираем 'import pygame' отсюда ---
import traceback

from game_engine_restructured.world_actor import WorldActor
from game_engine_restructured.core.preset import load_preset
from game_engine_restructured.world.processing.base_processor import BaseGenerator
from game_engine_restructured.world.regions import RegionManager

from pygame_tester.config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, BACKGROUND_COLOR, ARTIFACTS_ROOT,
    VIEWPORT_WIDTH, VIEWPORT_HEIGHT, MENU_WIDTH, PRESET_PATH
)
from pygame_tester.renderer import Renderer, Camera
from pygame_tester.ui import SideMenu
from pygame_tester.world_map_viewer import WorldMapViewer


def get_seed_from_console() -> int:
    while True:
        try:
            seed_str = input(">>> Enter world seed (e.g., 123) and press Enter: ")
            return int(seed_str) if seed_str else 123
        except ValueError:
            print("Invalid input. Please enter a number.")
            return 123


def main():
    # --- ИЗМЕНЕНИЕ: Переносим 'import pygame' сюда! ---
    import pygame

    print("--- Pygame World Viewer & Generator ---")
    city_seed = get_seed_from_console()

    # =======================================================
    # ШАГ 1: ГЕНЕРАЦИЯ МИРА
    # =======================================================
    print("\n--- World Generation Initializing ---")
    preset_data = json.loads(PRESET_PATH.read_text(encoding='utf-8'))
    preset = load_preset(preset_data)

    base_generator = BaseGenerator(preset)
    region_manager = RegionManager(city_seed, preset, base_generator, ARTIFACTS_ROOT)
    world_actor = WorldActor(city_seed, preset, ARTIFACTS_ROOT, progress_callback=print)

    world_actor.prepare_starting_area(region_manager)

    print("\n--- World Generation Complete. Starting Viewer ---")

    # =======================================================
    # ШАГ 2: ЗАПУСК ПРОСМОТРЩИКА
    # =======================================================
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Pygame World Viewer")
    clock = pygame.time.Clock()

    game_surface = pygame.Surface((VIEWPORT_WIDTH, VIEWPORT_HEIGHT))

    camera = Camera(VIEWPORT_WIDTH, VIEWPORT_HEIGHT)
    renderer = Renderer(screen)
    world_map = WorldMapViewer(ARTIFACTS_ROOT, city_seed)


    side_menu = SideMenu(SCREEN_WIDTH - MENU_WIDTH, 0, MENU_WIDTH, SCREEN_HEIGHT, world_map)

    running = True
    while running:
        try:
            dt = clock.tick(60) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                camera.handle_event(event)
                if side_menu.handle_event(event):
                    continue

            camera.process_inputs(dt)
            world_map.draw(game_surface, camera)
            renderer.draw_player_marker(game_surface)

            screen.fill(BACKGROUND_COLOR)
            screen.blit(game_surface, (0, 0))
            side_menu.draw(screen)
            renderer.draw_status(camera, world_map)
            renderer.draw_error_banner()

            pygame.display.flip()

        except Exception as e:
            error_msg = f"FATAL ERROR: {type(e).__name__}"
            print(f"{error_msg}: {e}")
            traceback.print_exc()
            renderer.set_error(error_msg)
            renderer.draw_error_banner()
            pygame.display.flip()
            pygame.time.wait(5000)
            running = False

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()