# editor/theme.py
# ==============================================================================
# Файл: editor/theme.py
# ВЕРСИЯ 4.4 (HOTFIX): Исправлена глобальная тема.
# - Добавлено правило для QWidget, QDialog, чтобы фон по умолчанию был темным.
# ==============================================================================

PALETTE = {
    "window_bg": "#3c3c3c",
    "editor_bg": "#2b2b2b",
    "dock_bg": "#323232",
    "text_color": "#ffffff",
    "prop_text_color": "#ffffff",
    "border_color": "#606060",
    "item_selected_bg": "#556677",
    "cat_pipeline_bg": "rgba(40, 40, 80, 100)",
    "cat_effects_bg": "rgba(90, 50, 30, 100)",
    "cat_math_bg": "rgba(40, 60, 90, 100)",
    "cat_modules_bg": "rgba(25, 80, 30, 100)",
    "cat_noises_bg": "rgba(80, 25, 30, 100)",
    "cat_instructions_bg": "rgba(60, 60, 60, 100)",
    "disabled_text_color": "#b3b3b3",
    "button_bg": "#445566",
    "button_hover": "#6a7b8d",
    "button_pressed": "#334455",
    "list_bg": "#2b2b2b",
}

APP_STYLE_SHEET = f"""
    /* Общий стиль для всего приложения */
    * {{
        font-family: Arial, sans-serif;
        font-size: 10pt;
        color: {PALETTE['text_color']};
    }}

    /* --- РЕФАКТОРИНГ: Базовый фон для всех виджетов --- */
    QWidget, QDialog {{
        background-color: {PALETTE['window_bg']};
    }}

    /* QMainWindow (переопределяет QWidget) */
    QMainWindow {{
        background-color: {PALETTE['window_bg']};
    }}

    /* QDockWidget (переопределяет QWidget) */
    QDockWidget {{
        background-color: {PALETTE['dock_bg']};
        color: {PALETTE['text_color']};
        titlebar-close-icon: none;
    }}
    QDockWidget::title {{
        background: {PALETTE['window_bg']};
        text-align: center;
        padding: 4px;
        border: 1px solid {PALETTE['border_color']};
    }}

    /* QMenuBar и QMenu */
    QMenuBar {{
        background-color: {PALETTE['dock_bg']};
    }}
    QMenuBar::item:selected {{
        background-color: {PALETTE['border_color']};
    }}
    QMenu {{
        background-color: {PALETTE['dock_bg']};
        border: 1px solid {PALETTE['border_color']};
    }}
    QMenu::item:selected {{
        background-color: {PALETTE['border_color']};
    }}

    /* QTreeView и NodesTreeWidget (палитра нодов) */
    NodesTreeWidget, QTreeView {{
        background-color: {PALETTE['list_bg']};
        border: 1px solid {PALETTE['border_color']};
        border-radius: 4px;
    }}
    QTreeView::item {{
        padding: 4px 0px;
        border-bottom: 1px solid {PALETTE['border_color']};
    }}
    QTreeView::item:selected {{
        background-color: {PALETTE['item_selected_bg']};
    }}
    QTabWidget {{
        background-color: {PALETTE['dock_bg']};
        border: none;
    }}
    QTabWidget::pane {{
        border: 1px solid {PALETTE['border_color']};
    }}
    QTabBar::tab {{
        background-color: {PALETTE['window_bg']};
        padding: 4px 8px;
        border: 1px solid {PALETTE['border_color']};
        border-bottom: none;
    }}
    QTabBar::tab:selected {{
        background-color: {PALETTE['dock_bg']};
    }}

    #AccordionProperties, PropertiesBinWidget {{
        background-color: {PALETTE['dock_bg']};
        border: none;
    }}
    #AccordionProperties QWidget, PropertiesBinWidget QWidget {{
        background-color: {PALETTE['dock_bg']};
        padding: 0px;
    }}

    QGroupBox#CollapsibleBox {{
        background-color: #323232;
        border: 1px solid #606060;
        border-radius: 6px;
        margin: 8px 6px;
        padding: 12px 8px 8px 8px;
        /* min-height: 0;  <-- ЭТА СТРОКА УДАЛЕНА */
    }}
    
    QGroupBox#CollapsibleBox::title {{
        subcontrol-origin: padding;
        subcontrol-position: top left;
        background: transparent;
        border: none;
        padding: 0 6px 0 28px;
        margin: 0;
        color: #e6e6e6;
        font-weight: bold;
    }}

    QGroupBox#CollapsibleBox::indicator {{
        subcontrol-origin: padding;
        subcontrol-position: top left;
        left: 6px;
        top: -1px;
        width: 16px;
        height: 16px;
        margin: 0;
    }}
    QGroupBox#CollapsibleBox::indicator:unchecked {{
        border: 1px solid #606060;
        background: #3c3c3c;
        border-radius: 3px;
    }}
    QGroupBox#CollapsibleBox::indicator:checked {{
        border: 1px solid #606060;
        background: #556677;
        border-radius: 3px;
    }}

    #AccordionProperties QLineEdit,
    #AccordionProperties QComboBox,
    #AccordionProperties QDoubleSpinBox,
    #AccordionProperties QSpinBox {{
        min-height: 20px;
        min-width: 72px;
        max-width: 110px;
        padding: 2px 4px;
        background-color: #2b2b2b;
        color: #ffffff;
        border: 1px solid #606060;
    }}
    #AccordionProperties QLineEdit:disabled,
    #AccordionProperties QComboBox:disabled,
    #AccordionProperties QDoubleSpinBox:disabled,
    #AccordionProperties QSpinBox:disabled {{
        color: {PALETTE['disabled_text_color']};
        background-color: #3f3f3f;
    }}
    
    #AccordionProperties QAbstractSpinBox::up-button,
    #AccordionProperties QAbstractSpinBox::down-button {{
        width: 0px;
        height: 0px;
        margin: 0;
        padding: 0;
        border: none;
    }}

    #AccordionProperties QLabel {{
        color: {PALETTE['text_color']};
        padding: 2px 0px 0px 0px;
        min-height: 20px;
    }}
    #AccordionProperties QLabel:disabled {{
        color: {PALETTE['disabled_text_color']};
    }}
    #AccordionProperties QCheckBox {{
        color: {PALETTE['text_color']};
        padding: 2px 0px;
        min-height: 20px;
    }}
    #AccordionProperties QCheckBox:disabled {{
        color: {PALETTE['disabled_text_color']};
    }}

    QPushButton {{
        background-color: {PALETTE['button_bg']};
        color: {PALETTE['text_color']};
        border: 1px solid {PALETTE['border_color']};
        padding: 4px;
        border-radius: 4px;
    }}
    QPushButton:hover {{
        background-color: {PALETTE['button_hover']};
    }}
    QPushButton:pressed {{
        background-color: {PALETTE['button_pressed']};
    }}
    QPushButton:disabled {{
        background-color: #3f3f3f;
        color: {PALETTE['disabled_text_color']};
    }}

    QListWidget {{
        background-color: {PALETTE['list_bg']};
        color: {PALETTE['text_color']};
        border: 1px solid {PALETTE['border_color']};
        border-radius: 4px;
    }}
    QListWidget::item:selected {{
        background-color: {PALETTE['item_selected_bg']};
    }}

    QGraphicsView {{
        background-color: {PALETTE['dock_bg']};
        border: none;
    }}

    QScrollArea {{
        background-color: {PALETTE['dock_bg']};
        border: none;
    }}

    #TopTabsLeft QLineEdit,
    #TopTabsLeft QSpinBox,
    #TopTabsLeft QDoubleSpinBox,
    #TopTabsLeft QComboBox,
    #TopTabsLeft QAbstractSpinBox {{
        background-color: #2b2b2b;
        color: #ffffff;
        border: 1px solid #606060;
        border-radius: 4px;
        padding: 2px 4px;
        selection-background-color: #556677;
    }}
    #TopTabsLeft QLineEdit:disabled,
    #TopTabsLeft QSpinBox:disabled,
    #TopTabsLeft QDoubleSpinBox:disabled,
    #TopTabsLeft QComboBox:disabled,
    #TopTabsLeft QAbstractSpinBox:disabled {{
        color: #b3b3b3;
        background-color: #3f3f3f;
        border-color: #555555;
    }}

    #RightOutliner QLineEdit {{
        background-color: #2b2b2b;
        color: #ffffff;
        border: 1px solid #606060;
        border-radius: 4px;
        padding: 2px 4px;
        selection-background-color: #556677;
    }}

    #LeftNodesPalette QLineEdit {{
        background-color: #2b2b2b;
        color: #ffffff;
        border: 1px solid #606060;
        border-radius: 4px;
        padding: 2px 4px;
        selection-background-color: #556677;
    }}

    #NodesPaletteSearch {{
        background-color: #2b2b2b;
        color: #ffffff;
        border: 1px solid #606060;
        border-radius: 4px;
        padding: 2px 4px;
        selection-background-color: #556677;
    }}
    #NodesPaletteSearch[placeholderText]:!focus {{
        color: #cccccc;
    }}

    #TopTabsRight::pane {{
        border: 1px solid #3e3e3e;
        border-radius: 4px;
    }}
    #TopTabsRight QTabBar::tab {{
        padding: 5px 10px;
        background: #2b2b2b;
        border: 1px solid #3e3e3e;
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        color: #ddd;
        margin-right: 2px;
    }}
    #TopTabsRight QTabBar::tab:selected {{
        background: #3a3a3a;
        color: #fff;
    }}
    
    #TopTabsRight QLineEdit,
    #TopTabsRight QSpinBox,
    #TopTabsRight QDoubleSpinBox,
    #TopTabsRight QComboBox,
    #TopTabsRight QAbstractSpinBox,
    #NodeInspector QLineEdit,
    #NodeInspector QSpinBox,
    #NodeInspector QDoubleSpinBox,
    #NodeInspector QComboBox,
    #NodeInspector QAbstractSpinBox {{
        background-color: #2b2b2b;
        color: #ffffff;
        border: 1px solid #606060;
        border-radius: 4px;
        padding: 2px 4px;
        selection-background-color: #556677;
    }}

    #NodeInspector QListWidget {{
        background-color: #2b2b2b;
        color: #ffffff;
        border: 1px solid #404040;
    }}
    #NodeInspector QListWidget::item:selected {{
        background: #3a3a3a;
    }}
"""
