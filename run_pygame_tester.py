from __future__ import annotations
import sys
import pathlib
import json
import pygame
import traceback

# --- Основные компоненты нашей архитектуры ---
from game_engine.world_actor import WorldActor
from game_engine.core.preset import load_preset
from game_engine.generators._base.generator import BaseGenerator
from game_engine.world_structure.regions import RegionManager
from game_engine.game_logic.world import GameWorld

# --- Компоненты Pygame ---
from pygame_tester.renderer import Renderer
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
from game_engine.core.grid.hex import HexGridSpec
from pygame_tester.renderer import Camera

# --- Настройка путей ---
ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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

    world_actor.prepare_starting_area(region_manager)

    print("\n--- World Generation Complete. Starting Game Client ---")

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Pygame World Tester")
    clock = pygame.time.Clock()

    # --- ИСПРАВЛЕНИЕ: Рассчитываем meters_per_pixel заранее ---
    # Получаем edge_m из пресета
    edge_m = 0.63
    hex_size_px = TILE_SIZE / 2
    meters_per_pixel = edge_m / hex_size_px

    # Создаем единый экземпляр HexGridSpec с правильными значениями
    grid_spec = HexGridSpec(
        edge_m=edge_m,
        meters_per_pixel=meters_per_pixel,
        chunk_px=CHUNK_SIZE
    )

    game_world = GameWorld(city_seed, grid_spec)
    # --- ИСПРАВЛЕНИЕ: Создаем экземпляр Camera и передаем его в Renderer ---
    camera = Camera(grid_spec)
    renderer = Renderer(screen, grid_spec, camera)
    side_menu = SideMenu(x=0, y=0, width=MENU_WIDTH, height=SCREEN_HEIGHT, renderer=renderer)

    viewport_width = SCREEN_WIDTH - MENU_WIDTH
    viewport_height = SCREEN_HEIGHT
    game_surface = pygame.Surface((viewport_width, viewport_height))
    running = True

    def safe_draw():
        try:
            # Game logic and rendering
            dt = clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    nonlocal running
                    running = False
                if side_menu.handle_event(event):
                    continue
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse_x, mouse_y = event.pos
                    if mouse_x > MENU_WIDTH:
                        world_x = renderer.camera.top_left_wx + (
                                    mouse_x - MENU_WIDTH) * renderer.grid_spec.meters_per_pixel
                        world_z = renderer.camera.top_left_wz + mouse_y * renderer.grid_spec.meters_per_pixel
                        game_world.set_player_target(world_x, world_z)

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

            player_q, player_r = state["player_q"], state["player_r"]

            # --- ИСПРАВЛЕНИЕ: Вызываем center_on_player на объекте camera напрямую ---
            camera.center_on_player(player_q, player_r)

            screen.fill(BACKGROUND_COLOR)
            renderer.draw_error_banner()
            if state["path"]:
                renderer.draw_path(state["path"], game_surface)

            renderer.draw_player(player_q, player_r, game_surface)

            screen.blit(game_surface, (MENU_WIDTH, 0))

            player_wx, player_wz = grid_spec.axial_to_world(player_q, player_r)
            renderer.draw_status(state["world_manager"], player_wx, player_wz)

            chunk_size_m = grid_spec.chunk_size_m
            side_menu.draw(screen, state["world_manager"],
                           int(player_wx // chunk_size_m),
                           int(player_wz // chunk_size_m))

            pygame.display.flip()

        except Exception as e:
            renderer.set_error(f"FATAL RENDER ERROR: {type(e).__name__}: {e}")
            renderer.draw_error_banner()
            pygame.display.flip()
            traceback.print_exc()

    while running:
        safe_draw()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()