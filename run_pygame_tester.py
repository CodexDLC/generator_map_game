# Файл: run_pygame_tester.py
from __future__ import annotations
import sys
import pathlib
import json
import pygame
import traceback

# --- НАЧАЛО ИЗМЕНЕНИЙ ---

# Теперь мы импортируем все из реструктурированного движка
from game_engine_restructured.world_actor import WorldActor
from game_engine_restructured.core.preset import load_preset
from game_engine_restructured.generators.base.generator import BaseGenerator
from game_engine_restructured.world.regions import RegionManager
from game_engine_restructured.core.grid.hex import HexGridSpec

# Логика игры (GameWorld) теперь является частью тестера
from pygame_tester.game_logic.world import GameWorld
from pygame_tester.renderer import Renderer, Camera
from pygame_tester.config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, BACKGROUND_COLOR, CHUNK_SIZE,
    MENU_WIDTH, ARTIFACTS_ROOT, PRESET_PATH
)
from pygame_tester.ui import SideMenu

# --- КОНЕЦ ИЗМЕНЕНИЙ ---


ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))



def get_seed_from_console() -> int:
    while True:
        try:
            seed_str = input(">>> Enter world seed (e.g., 123) and press Enter: ")
            return int(seed_str) if seed_str else 123
        except ValueError:
            print("Invalid input. Please enter a number.")


def main():
    print("--- World Generation Initializing ---")
    city_seed = get_seed_from_console()

    # --- ИЗМЕНЕНИЕ: Путь к пресету теперь ведет в новую папку data ---
    preset_path = ROOT / "game_engine_restructured" / "data" / "presets" / "world" / "base_default.json"
    preset_data = json.loads(preset_path.read_text())
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

    grid_spec = HexGridSpec(edge_m=0.63, meters_per_pixel=0.5, chunk_px=CHUNK_SIZE)

    game_world = GameWorld(city_seed, grid_spec)  # GameWorld теперь из pygame_tester
    camera = Camera(grid_spec)
    renderer = Renderer(screen, grid_spec, camera)
    side_menu = SideMenu(x=SCREEN_WIDTH - MENU_WIDTH, y=0, width=MENU_WIDTH, height=SCREEN_HEIGHT, renderer=renderer)
    game_surface = pygame.Surface((SCREEN_WIDTH - MENU_WIDTH, SCREEN_HEIGHT))

    running = True
    while running:
        try:
            dt = clock.tick(60) / 1000.0

            # --- Обработка событий ---
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if side_menu.handle_event(event):
                    continue

                if event.type == pygame.MOUSEWHEEL:
                    camera.change_zoom(event.y * 0.1, pygame.mouse.get_pos())

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse_x, mouse_y = event.pos
                    if mouse_x < game_surface.get_width():
                        world_x, world_z = renderer.screen_to_world(mouse_x, mouse_y)
                        game_world.set_player_target(world_x, world_z)

                # --- ИЗМЕНЕНИЕ: Движение игрока по нажатию клавиш ---
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_w: game_world.move_player_by(0, -1)  # North-West
                    if event.key == pygame.K_s: game_world.move_player_by(0, 1)  # South-East
                    if event.key == pygame.K_a: game_world.move_player_by(-1, 0)  # West
                    if event.key == pygame.K_d: game_world.move_player_by(1, 0)  # East
                    # Добавим диагонали для удобства
                    if event.key == pygame.K_q: game_world.move_player_by(-1, 1)  # South-West
                    if event.key == pygame.K_e: game_world.move_player_by(1, -1)  # North-East

            game_world.update(dt)
            state = game_world.get_render_state()
            player_q, player_r = state["player_q"], state["player_r"]

            # Камера всегда следует за игроком
            camera.center_on_player(player_q, player_r)

            # Отрисовка
            renderer.draw_world(game_world, game_surface)
            if state["path"]:
                renderer.draw_path(state["path"], game_surface)
            renderer.draw_player(player_q, player_r, game_surface)

            screen.fill(BACKGROUND_COLOR)
            screen.blit(game_surface, (0, 0))

            player_wx, player_wz = grid_spec.axial_to_world(player_q, player_r)
            side_menu.draw(screen, state["world_manager"],
                           *grid_spec.axial_to_chunk_coords(player_q, player_r))
            renderer.draw_status(state["world_manager"], player_wx, player_wz, player_q, player_r)
            renderer.draw_error_banner()

            pygame.display.flip()

        except Exception as e:
            # (обработка ошибок без изменений)
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