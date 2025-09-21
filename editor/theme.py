# ==============================================================================
# Файл: editor/theme.py
# Назначение: Хранит константы цветов и стилей для UI редактора.
# ==============================================================================

# Цветовая палитра в формате HEX
PALETTE = {
    "window_bg": "#3c3c3c",       # Цвет фона окна
    "editor_bg": "#2b2b2b",       # Цвет фона самого редактора нодов
    "dock_bg": "#323232",         # Цвет фона панелей
    "text_color": "#dcdcdc",      # Основной цвет текста
    "border_color": "#555555",    # Цвет границ
}

# Глобальный стиль приложения в формате Qt StyleSheet (похож на CSS)
APP_STYLE_SHEET = f"""
    QMainWindow {{
        background-color: {PALETTE['window_bg']};
    }}
    QDockWidget {{
        background-color: {PALETTE['dock_bg']};
        color: {PALETTE['text_color']};
        titlebar-close-icon: none; /* Убираем кнопку закрытия с панелей */
    }}
    QDockWidget::title {{
        background: {PALETTE['window_bg']};
        text-align: center;
        padding: 4px;
        border: 1px solid {PALETTE['border_color']};
    }}
    QMenuBar {{
        background-color: {PALETTE['dock_bg']};
        color: {PALETTE['text_color']};
    }}
    QMenuBar::item:selected {{
        background-color: {PALETTE['border_color']};
    }}
    QMenu {{
        background-color: {PALETTE['dock_bg']};
        color: {PALETTE['text_color']};
        border: 1px solid {PALETTE['border_color']};
    }}
    QMenu::item:selected {{
        background-color: {PALETTE['border_color']};
    }}
"""