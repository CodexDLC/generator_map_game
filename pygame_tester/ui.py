# pygame_tester/ui.py
import pygame
import pathlib


# --- НАЧАЛО ИЗМЕНЕНИЯ: Копируем класс Minimap из renderer.py сюда ---
class Minimap:
    def __init__(self, x, y):
        self.map_size_chunks = 5
        self.cell_size_px = 32
        self.map_pixel_size = self.map_size_chunks * self.cell_size_px
        self.position = (x, y)
        self.image_cache: dict[pathlib.Path, pygame.Surface] = {}
        self.visible = False

    def _get_preview_image(
        self, world_manager, cx: int, cz: int
    ) -> pygame.Surface | None:
        path = (
            world_manager._get_chunk_path(
                world_manager.world_id, world_manager.current_seed, cx, cz
            )
            / "preview.png"
        )
        if path in self.image_cache:
            return self.image_cache[path]
        try:
            image = pygame.image.load(str(path)).convert()
            scaled_image = pygame.transform.scale(
                image, (self.cell_size_px, self.cell_size_px)
            )
            self.image_cache[path] = scaled_image
            return scaled_image
        except (pygame.error, FileNotFoundError):
            return None

    def draw(self, screen, world_manager, player_cx: int, player_cz: int):
        if not self.visible:
            return

        map_surface = pygame.Surface((self.map_pixel_size, self.map_pixel_size))
        map_surface.fill((20, 20, 30))
        map_surface.set_alpha(220)
        center_offset = self.map_size_chunks // 2
        for y in range(self.map_size_chunks):
            for x in range(self.map_size_chunks):
                chunk_cx = player_cx + x - center_offset
                chunk_cz = player_cz + y - center_offset
                img = self._get_preview_image(world_manager, chunk_cx, chunk_cz)
                if img:
                    map_surface.blit(
                        img, (x * self.cell_size_px, y * self.cell_size_px)
                    )

        pygame.draw.rect(map_surface, (100, 100, 120), map_surface.get_rect(), 1)
        player_marker_rect = (
            center_offset * self.cell_size_px,
            center_offset * self.cell_size_px,
            self.cell_size_px,
            self.cell_size_px,
        )
        pygame.draw.rect(map_surface, (255, 255, 0), player_marker_rect, 2)
        screen.blit(map_surface, self.position)

    def toggle_visibility(self):
        self.visible = not self.visible


# --- КОНЕЦ ИЗМЕНЕНИЯ ---


class Button:
    # ... (код класса Button без изменений) ...
    def __init__(self, x, y, width, height, text, callback):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.callback = callback
        self.font = pygame.font.Font(None, 28)
        self.color_bg = pygame.Color("grey30")
        self.color_border = pygame.Color("grey60")
        self.color_text = pygame.Color("white")
        self.is_hovered = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.is_hovered:
                self.callback()
                return True
        return False

    def draw(self, screen):
        bg_color = pygame.Color("grey40") if self.is_hovered else self.color_bg
        pygame.draw.rect(screen, bg_color, self.rect)
        pygame.draw.rect(screen, self.color_border, self.rect, 2)
        text_surf = self.font.render(self.text, True, self.color_text)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)


class SideMenu:
    def __init__(self, x, y, width, height):
        self.rect = pygame.Rect(x, y, width, height)
        self.buttons = []
        self.button_height = 40
        self.padding = 10
        # --- НАЧАЛО ИЗМЕНЕНИЯ: Делаем фон непрозрачным ---
        self.bg_color = pygame.Color(40, 45, 55)
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

        # --- НАЧАЛО ИЗМЕНЕНИЯ: Добавляем миникарту ---
        minimap_y = (
            self.rect.y
            + self.padding
            + 2 * (self.button_height + self.padding)
            + self.padding
        )
        self.minimap = Minimap(self.rect.x + (self.rect.width - 160) // 2, minimap_y)
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    def add_button(self, text, callback):
        button_y = (
            self.rect.y
            + self.padding
            + len(self.buttons) * (self.button_height + self.padding)
        )
        button_x = self.rect.x + self.padding
        button_width = self.rect.width - (2 * self.padding)
        button = Button(
            button_x, button_y, button_width, self.button_height, text, callback
        )
        self.buttons.append(button)

    def handle_event(self, event):
        for button in self.buttons:
            if button.handle_event(event):
                return True
        return False

    def draw(self, screen, world_manager, player_cx, player_cz):
        """Отрисовывает фон меню, все кнопки и миникарту."""
        pygame.draw.rect(screen, self.bg_color, self.rect)
        for button in self.buttons:
            button.draw(screen)

        # --- НАЧАЛО ИЗМЕНЕНИЯ: Отрисовываем миникарту ---
        self.minimap.draw(screen, world_manager, player_cx, player_cz)
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---
