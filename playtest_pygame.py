#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, pygame, pathlib
from typing import Dict, Tuple, Optional, List

from engine.worldgen_core.base.constants import DEFAULT_PALETTE

# --- Подключаем наш основной движок и контроллер ---
sys.path.append(os.path.dirname(__file__))
from worldgen_ui.tabs.world.state import WorldState
from worldgen_ui.tabs.world.controller import WorldController
from engine.worldgen_core.pathfinding_ai.a_star import find_path


# ---------------- CONFIG ----------------
TILE_SIZE = 5
MAP_SIZE_TILES = 128
SCREEN_WIDTH = MAP_SIZE_TILES * TILE_SIZE
SCREEN_HEIGHT = MAP_SIZE_TILES * TILE_SIZE


# ---------------- HELPERS ----------------
def hex_to_rgb(s: str) -> Tuple[int, int, int]:
    s = s.lstrip("#")
    if len(s) == 8: s = s[2:]
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


# --- ГЛАВНЫЙ КЛАСС ИГРЫ ---
class PygameViewer:
    def __init__(self, seed: int):
        # --- Инициализация Pygame ---
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Pygame World Viewer")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 16)

        # --- Инициализация нашего движка ---
        self.state = WorldState(city_seed=seed)
        self.ctrl = WorldController(self.state)
        self.current_chunk_data = self.ctrl.load_center()

        # --- Игрок ---
        self.player_pos = (MAP_SIZE_TILES // 2, MAP_SIZE_TILES // 2)
        self.player_path: List[Tuple[int, int]] = []

        # --- Цвета ---
        self.colors = {k: hex_to_rgb(v) for k, v in DEFAULT_PALETTE.items()}

    def _get_tile_data(self):
        data = self.current_chunk_data
        layers = data.get("layers", {})
        kind_payload = layers.get("kind", {})
        from engine.worldgen_core.base.constants import ID_TO_KIND
        def decode(rows):
            grid = []
            for r in rows:
                line = []
                for v, c in r: line.extend([v] * int(c))
                grid.append(line)
            return grid

        if isinstance(kind_payload, dict) and kind_payload.get("encoding") == "rle_rows_v1":
            grid_ids = decode(kind_payload.get("rows", []))
            kind_grid = [[ID_TO_KIND.get(v, "ground") for v in row] for row in grid_ids]
        elif isinstance(kind_payload, list):
            if kind_payload and kind_payload[0] and isinstance(kind_payload[0][0], int):
                kind_grid = [[ID_TO_KIND.get(v, "ground") for v in row] for row in kind_payload]
            else:
                kind_grid = kind_payload
        else:
            kind_grid = [["ground"] * MAP_SIZE_TILES for _ in range(MAP_SIZE_TILES)]
        height_grid = layers.get("height_q", {}).get("grid", [])
        return kind_grid, height_grid

    def run(self):
        running = True
        while running:
            # --- Обработка ввода ---
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                self._handle_input(event)

            # --- Обновление логики ---
            self._update()

            # --- Отрисовка ---
            self._render()

        pygame.quit()

    def _handle_input(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_x, mouse_y = event.pos
            target_tile = (mouse_x // TILE_SIZE, mouse_y // TILE_SIZE)

            # Используем наш новый A* для поиска пути
            kind_grid, height_grid = self._get_tile_data()
            path = find_path(
                kind_grid=kind_grid,
                height_grid=height_grid,
                start_pos=self.player_pos,
                end_pos=target_tile
            )
            if path:
                self.player_path = path[1:]  # Убираем первую точку, т.к. мы уже на ней

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit(0)

            # Ручное перемещение
            dx, dz = 0, 0
            if event.key == pygame.K_w: dz = -1
            if event.key == pygame.K_s: dz = 1
            if event.key == pygame.K_a: dx = -1
            if event.key == pygame.K_d: dx = 1
            if dx != 0 or dz != 0:
                self.player_path = [(self.player_pos[0] + dx, self.player_pos[1] + dz)]

    def _update(self):
        # Движение игрока по пути
        if self.player_path:
            next_pos = self.player_path.pop(0)

            # Проверка выхода за пределы чанка
            if not (0 <= next_pos[0] < MAP_SIZE_TILES and 0 <= next_pos[1] < MAP_SIZE_TILES):
                dx = next_pos[0] - self.player_pos[0]
                dz = next_pos[1] - self.player_pos[1]

                if self.ctrl.can_move(dx, dz):
                    print(f"Переход в чанк: ({dx}, {dz})")
                    self.current_chunk_data = self.ctrl.move(dx, dz)

                    # Корректируем позицию игрока для нового чанка
                    new_x = (self.player_pos[0] + dx) % MAP_SIZE_TILES
                    new_y = (self.player_pos[1] + dz) % MAP_SIZE_TILES
                    self.player_pos = (new_x, new_y)
                    self.player_path = []  # Очищаем старый путь
                else:
                    print("Переход невозможен!")
                    self.player_path = []  # Очищаем путь, т.к. он ведет в тупик
            else:
                self.player_pos = next_pos

    def _render(self):
        self.screen.fill((0, 0, 0))

        # Отрисовка карты
        kind_grid, _ = self._get_tile_data()
        for z in range(MAP_SIZE_TILES):
            for x in range(MAP_SIZE_TILES):
                kind_name = kind_grid[z][x]
                color = self.colors.get(kind_name, (255, 0, 255))  # Розовый для ошибок
                rect = (x * TILE_SIZE, z * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                pygame.draw.rect(self.screen, color, rect)

        # Отрисовка пути
        for pos in self.player_path:
            rect = (pos[0] * TILE_SIZE, pos[1] * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            pygame.draw.rect(self.screen, (255, 255, 0, 100), rect)  # Желтый путь

        # Отрисовка игрока
        player_rect = (self.player_pos[0] * TILE_SIZE, self.player_pos[1] * TILE_SIZE, TILE_SIZE, TILE_SIZE)
        pygame.draw.rect(self.screen, (255, 255, 255), player_rect)

        # Отрисовка статуса
        status_text = f"World: {self.state.world_id} | Seed: {self.state.seed} | Coords: ({self.state.cx}, {self.state.cz})"
        text_surface = self.font.render(status_text, True, (255, 255, 255))
        self.screen.blit(text_surface, (5, SCREEN_HEIGHT - 20))

        pygame.display.flip()
        self.clock.tick(15)  # Ограничим скорость для пошагового движения


def main():
    # Простой экран для ввода сида
    seed_str = input("Введите Seed и нажмите Enter (пусто = 123): ")
    seed = int(seed_str) if seed_str.isdigit() else 123

    game = PygameViewer(seed)
    game.run()


if __name__ == "__main__":
    main()