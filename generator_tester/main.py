# generator_tester/main.py
import pygame


from generator_tester.config import SCREEN_WIDTH, SCREEN_HEIGHT, CHUNK_SIZE, TILE_SIZE, PLAYER_MOVE_SPEED, \
    BACKGROUND_COLOR
from generator_tester.renderer import Renderer
from generator_tester.world_manager import WorldManager


from engine.worldgen_core.pathfinding_ai.a_star import find_path


class Game:
    def __init__(self, seed: int):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Generator Tester")
        self.clock = pygame.time.Clock()

        self.world_manager = WorldManager(city_seed=seed)
        self.renderer = Renderer(self.screen)

        self.player_pos = (CHUNK_SIZE // 2, CHUNK_SIZE // 2)
        self.player_path = []
        self.move_timer = 0

    def run(self):
        running = True
        while running:
            delta_time = self.clock.tick(60) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                self._handle_input(event)

            self._update(delta_time)
            self._render()

        pygame.quit()

    def _handle_input(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_x, mouse_y = event.pos
            target_tile = (mouse_x // TILE_SIZE, mouse_y // TILE_SIZE)

            kind_grid, height_grid = self.world_manager.get_current_chunk_data()
            path = find_path(kind_grid, height_grid, self.player_pos, target_tile)

            if path:
                self.player_path = path[1:]

    def _update(self, delta_time: float):
        self.move_timer -= delta_time
        if self.player_path and self.move_timer <= 0:
            self.move_timer = PLAYER_MOVE_SPEED
            self.player_pos = self.player_path.pop(0)

            # Проверка перехода
            px, pz = self.player_pos
            dx, dz = 0, 0
            if px < 0:
                dx = -1
            elif px >= CHUNK_SIZE:
                dx = 1
            if pz < 0:
                dz = -1
            elif pz >= CHUNK_SIZE:
                dz = 1

            if dx != 0 or dz != 0:
                if self.world_manager.move(dx, dz):
                    self.player_pos = (px % CHUNK_SIZE, pz % CHUNK_SIZE)
                    self.player_path = []  # Сбрасываем путь при переходе

    def _render(self):
        self.screen.fill(BACKGROUND_COLOR)

        kind_grid, _ = self.world_manager.get_current_chunk_data()

        self.renderer.draw_world(kind_grid)
        self.renderer.draw_path(self.player_path)
        self.renderer.draw_player(self.player_pos)
        self.renderer.draw_status(self.world_manager)

        pygame.display.flip()


if __name__ == '__main__':
    start_seed = int(input("Введите Seed и нажмите Enter (пусто = 123): "))
    game = Game(start_seed)
    game.run()