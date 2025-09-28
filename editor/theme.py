# editor/theme.py
# ==============================================================================
# Файл: editor/theme.py
# Назначение: Хранит константы цветов и стилей для UI редактора.
# ВЕРСИЯ 2.0: Добавлены продвинутые стили для QTreeView (палитры нодов).
# ==============================================================================

PALETTE = {
    "window_bg": "#3c3c3c",
    "editor_bg": "#2b2b2b",
    "dock_bg": "#323232",
    "text_color": "#dcdcdc",
    "border_color": "#555555",
    "item_selected_bg": "#556677",
    # --- НОВЫЕ ЦВЕТА ДЛЯ КАТЕГОРИЙ НОД ---
    "cat_pipeline_bg": "rgba(40, 40, 80, 50)",  # Сине-фиолетовый для пайплайна
    "cat_effects_bg": "rgba(90, 50, 30, 50)",   # Оранжевый для эффектов
    "cat_math_bg": "rgba(40, 60, 90, 50)",      # Синий для математики
    "cat_modules_bg": "rgba(25, 80, 30, 50)",   # Зеленый для модулей
    "cat_noises_bg": "rgba(80, 25, 30, 50)",    # Красный для шумов
    "cat_instructions_bg": "rgba(60, 60, 60, 50)", # Серый для инструкций
}

APP_STYLE_SHEET = f"""
    /* ... (все старые стили до QTreeView остаются без изменений) ... */
    QMainWindow {{ background-color: {PALETTE['window_bg']}; }}
    QDockWidget {{ background-color: {PALETTE['dock_bg']}; color: {PALETTE['text_color']}; titlebar-close-icon: none; }}
    QDockWidget::title {{ background: {PALETTE['window_bg']}; text-align: center; padding: 4px; border: 1px solid {PALETTE['border_color']}; }}
    QMenuBar {{ background-color: {PALETTE['dock_bg']}; color: {PALETTE['text_color']}; }}
    QMenuBar::item:selected {{ background-color: {PALETTE['border_color']}; }}
    QMenu {{ background-color: {PALETTE['dock_bg']}; color: {PALETTE['text_color']}; border: 1px solid {PALETTE['border_color']}; }}
    QMenu::item:selected {{ background-color: {PALETTE['border_color']}; }}

    /* --- НОВЫЕ ПРОДВИНУТЫЕ СТИЛИ ДЛЯ ПАЛИТРЫ НОД --- */
    NodesTreeWidget {{
        background-color: {PALETTE['dock_bg']};
        border: none;
    }}
    QTreeView {{
        background-color: {PALETTE['dock_bg']};
        color: {PALETTE['text_color']};
        border: none;
        font-size: 10pt;
    }}
    QTreeView::item {{
        padding: 4px 0px; /* Добавляем отступы для нод */
    }}
    QTreeView::item:selected {{
        background-color: {PALETTE['item_selected_bg']};
        color: white;
    }}
    /* Стиль для "веток" - категорий */
    QTreeView::branch {{
        background-color: transparent;
    }}
    /* Стиль для названий категорий, делаем их похожими на кнопки */
    QTreeView::branch:has-children:!adjoins-item {{
        background-color: {PALETTE['window_bg']};
        border: 1px solid {PALETTE['border_color']};
        border-radius: 4px;
        margin: 3px 0px;
        padding: 3px;
    }}
    QTreeView::branch:selected {{
        background-color: {PALETTE['item_selected_bg']};
    }}
        /* --- Стили для панели свойств --- */
    PropertiesBinWidget QWidget {{
        background-color: {PALETTE['dock_bg']};
        border: none;
    }}
    PropertiesBinWidget QLineEdit, PropertiesBinWidget QComboBox {{
        background-color: {PALETTE['editor_bg']};
        color: {PALETTE['text_color']};
        border: 1px solid {PALETTE['border_color']};
        padding: 2px;
    }}
    PropertiesBinWidget QLabel {{
        color: {PALETTE['text_color']};
        padding-top: 4px;
    }}
    PropertiesBinWidget QCheckBox::indicator {{
        width: 14px;
        height: 14px;
    }}
    PropertiesBinWidget QTabWidget::pane {{
        border: 1px solid {PALETTE['border_color']};
    }}
    PropertiesBinWidget QTabBar::tab {{
        background: {PALETTE['dock_bg']};
        color: {PALETTE['text_color']};
        padding: 4px 8px;
        border: 1px solid {PALETTE['border_color']};
        border-bottom: none;
    }}
    PropertiesBinWidget QTabBar::tab:selected {{
        background: {PALETTE['window_bg']};
    }}
"""