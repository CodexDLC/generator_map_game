# editor/theme.py
# ==============================================================================
# Файл: editor/theme.py
# Назначение: Хранит константы цветов и стилей для UI редактора.
# ВЕРСИЯ 4.3: Исправлены отступы и наложения в панели свойств (#AccordionProperties и CollapsibleBox).
#             Убран box-shadow из-за несовместимости, добавлены точные margins/paddings.
#             Цветовая гамма синхронизирована с остальным приложением.
# ==============================================================================

PALETTE = {
    "window_bg": "#3c3c3c",  # Основной фон окна
    "editor_bg": "#2b2b2b",  # Фон полей ввода и редакторов
    "dock_bg": "#323232",    # Фон доков и панелей (согласно остальному интерфейсу)
    "text_color": "#ffffff", # Белый текст для единства с приложением
    "prop_text_color": "#ffffff",
    "border_color": "#606060",  # Границы для рамок
    "item_selected_bg": "#556677",
    # Цвета категорий нодов
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

    /* QMainWindow */
    QMainWindow {{
        background-color: {PALETTE['window_bg']};
    }}

    /* QDockWidget (для всех панелей) */
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

/* AccordionProperties и PropertiesBinWidget (панель свойств, фиксированные отступы) */
    #AccordionProperties, PropertiesBinWidget {{
        background-color: {PALETTE['dock_bg']};
        border: none;
    }}
    #AccordionProperties QWidget, PropertiesBinWidget QWidget {{
        background-color: {PALETTE['dock_bg']};
        padding: 0px;
    }}

    /* --- СЛИТНЫЙ CollapsibleBox: одна коробка, заголовок внутри padding --- */
    QGroupBox#CollapsibleBox {{
        background-color: #323232;      /* dock_bg */
        border: 1px solid #606060;
        border-radius: 6px;
        margin: 8px 6px;                /* зазор между секциями и краями дока */
        padding: 12px 8px 8px 8px;      /* РЕЗЕРВ под заголовок сверху */
        min-height: 0;                  /* без фикса высоты */
    }}
    
    /* Заголовок рисуем в области padding — «слит» с боксом */
    QGroupBox#CollapsibleBox::title {{
        subcontrol-origin: padding;     /* вместо margin */
        subcontrol-position: top left;
        background: transparent;        /* без отдельной плашки */
        border: none;                   /* рамку даёт сам бокс */
        padding: 0 6px 0 28px;          /* место под индикатор слева */
        margin: 0;
        color: #e6e6e6;
        font-weight: bold;
    }}

    /* Индикатор-чекбокс в заголовке */
    QGroupBox#CollapsibleBox::indicator {{
        subcontrol-origin: padding;
        subcontrol-position: top left;
        left: 6px;
        top: -1px;                      /* подровнять по вертикали */
        width: 16px;
        height: 16px;
        margin: 0;
    }}
    QGroupBox#CollapsibleBox::indicator:unchecked {{
        border: 1px solid #606060;
        background: #3c3c3c;            /* window_bg */
        border-radius: 3px;
    }}
    QGroupBox#CollapsibleBox::indicator:checked {{
        border: 1px solid #606060;
        background: #556677;            /* item_selected_bg */
        border-radius: 3px;
    }}

    /* Поля внутри панели — растягиваемые, без душащего max-width */
    #AccordionProperties QLineEdit,
    #AccordionProperties QComboBox,
    #AccordionProperties QDoubleSpinBox,
    #AccordionProperties QSpinBox {{
        min-height: 20px;
        min-width: 72px;
        max-width: 110px;   /* компактно для цифр */
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
    
        /* Кнопки спинбоксов скрываем: поле выглядит как узкий инпут */
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
        min-height: 20px;  /* Фиксированная высота меток */
    }}
    #AccordionProperties QLabel:disabled {{
        color: {PALETTE['disabled_text_color']};
    }}
    #AccordionProperties QCheckBox {{
        color: {PALETTE['text_color']};
        padding: 2px 0px;
        min-height: 20px;  /* Фиксированная высота чекбоксов */
    }}
    #AccordionProperties QCheckBox:disabled {{
        color: {PALETTE['disabled_text_color']};
    }}

    /* QPushButton (для других панелей) */
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

    /* QListWidget (region_presets_panel.py) */
    QListWidget {{
        background-color: {PALETTE['list_bg']};
        color: {PALETTE['text_color']};
        border: 1px solid {PALETTE['border_color']};
        border-radius: 4px;
    }}
    QListWidget::item:selected {{
        background-color: {PALETTE['item_selected_bg']};
    }}

    /* QGraphicsView (central_graph.py) */
    QGraphicsView {{
        background-color: {PALETTE['dock_bg']};
        border: none;
    }}

    /* QScrollArea (для всех прокруток) */
    QScrollArea {{
        background-color: {PALETTE['dock_bg']};
        border: none;
    }}
"""