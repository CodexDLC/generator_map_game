# ==============================================================================
# Файл: editor/ui_panels/compute_panel.py
# Назначение: Модуль для создания панели с кнопками вычисления (Apply).
# ВЕРСИЯ 1.2: Добавлен objectName.
# ==============================================================================
from PySide6 import QtWidgets, QtCore

from ..actions.compute_actions import on_apply_clicked, on_apply_tiled_clicked


def create_compute_dock(main_window) -> None:
    """
    Создает и настраивает док-виджет с кнопками APPLY.
    """
    compute_widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(compute_widget)
    layout.setContentsMargins(4, 8, 4, 8)

    apply_button = QtWidgets.QPushButton("APPLY")
    apply_button.setFixedHeight(40)

    apply_tiled_button = QtWidgets.QPushButton("APPLY (tiled)")
    apply_tiled_button.setFixedHeight(36)

    layout.addWidget(apply_button)
    layout.addWidget(apply_tiled_button)
    layout.addStretch()

    apply_button.clicked.connect(lambda: on_apply_clicked(main_window))
    apply_tiled_button.clicked.connect(lambda: on_apply_tiled_clicked(main_window))

    dock = QtWidgets.QDockWidget("Вычисление", main_window)
    dock.setObjectName("Панель 'Вычисление'")
    dock.setWidget(compute_widget)

    main_window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)

    main_window.apply_button = apply_button
    main_window.apply_tiled_button = apply_tiled_button
