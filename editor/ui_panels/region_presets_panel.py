# editor/ui_panels/region_presets_panel.py
from PySide6 import QtWidgets, QtCore


def create_region_presets_dock(main_window) -> None:
    """
    Создает док-виджет для управления пресетами регионов проекта.
    """
    presets_widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(presets_widget)
    layout.setContentsMargins(4, 8, 4, 8)

    main_window.presets_list_widget = QtWidgets.QListWidget()
    layout.addWidget(main_window.presets_list_widget)

    button_layout = QtWidgets.QHBoxLayout()
    new_button = QtWidgets.QPushButton("+")
    new_button.setToolTip("Создать новый пресет региона")
    save_button = QtWidgets.QPushButton("Сохранить")
    save_button.setToolTip("Сохранить активный пресет")
    delete_button = QtWidgets.QPushButton("-")
    delete_button.setToolTip("Удалить выбранный пресет")

    button_layout.addWidget(new_button)
    button_layout.addWidget(save_button)
    button_layout.addWidget(delete_button)
    layout.addLayout(button_layout)

    dock = QtWidgets.QDockWidget("Пресеты Региона", main_window)
    dock.setWidget(presets_widget)

    main_window.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, dock)

    # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
    # Сохраняем ссылку на созданный док-виджет, чтобы к нему можно было обращаться
    main_window.dock_region_presets = dock
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---