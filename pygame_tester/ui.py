# pygame_tester/ui.py
import pygame
from typing import List


class Button:
    # ... (Код класса Button остается без изменений) ...
    def __init__(self, x, y, width, height, text, callback):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.callback = callback
        self.font = pygame.font.Font(None, 24)
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
    def __init__(self, x, y, width, height, world_map_viewer):
        self.rect = pygame.Rect(x, y, width, height)
        self.buttons: List[Button] = []
        self.button_height = 40
        self.padding = 10
        self.bg_color = pygame.Color(40, 45, 55, 240)
        self.world_map_viewer = world_map_viewer

        self.layer_modes = self.world_map_viewer.get_available_layers()
        self.current_layer_index = 0

        self.add_button(self._get_layer_button_text(), self.toggle_layer_mode)
        # Можно добавить еще кнопки в будущем

    def _get_layer_button_text(self):
        mode_name = self.layer_modes[self.current_layer_index]
        return f"Layer: {mode_name.capitalize()}"

    def add_button(self, text, callback):
        button_y = self.rect.y + self.padding + len(self.buttons) * (self.button_height + self.padding)
        button_x = self.rect.x + self.padding
        button_width = self.rect.width - (2 * self.padding)
        button = Button(button_x, button_y, button_width, self.button_height, text, callback)
        self.buttons.append(button)

    def handle_event(self, event):
        for button in self.buttons:
            if button.handle_event(event):
                return True
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            if self.rect.collidepoint(event.pos):
                return True
        return False

    def draw(self, screen):
        menu_surface = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        pygame.draw.rect(menu_surface, self.bg_color, menu_surface.get_rect(), border_radius=8)
        screen.blit(menu_surface, self.rect.topleft)

        for button in self.buttons:
            button.draw(screen)

    def toggle_layer_mode(self):
        self.current_layer_index = (self.current_layer_index + 1) % len(self.layer_modes)
        new_layer = self.layer_modes[self.current_layer_index]
        self.world_map_viewer.set_active_layer(new_layer)
        self.buttons[0].text = self._get_layer_button_text()