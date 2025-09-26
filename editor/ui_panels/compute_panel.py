# ==============================================================================
# Файл: editor/ui_panels/compute_panel.py
# Назначение: Панель запуска вычислений (теперь только цельный расчёт).
# ВЕРСИЯ 2.0: Убрана кнопка "APPLY (tiled)". Оставляем только "APPLY".
#             Для совместимости main_window.apply_tiled_button = None.
# ==============================================================================
from PySide6 import QtWidgets, QtCore


def create_compute_dock(main_window) -> None:
    """
    Создает и настраивает док-виджет с кнопкой APPLY (без тайлового запуска).
    """
    compute_widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(compute_widget)
    layout.setContentsMargins(4, 8, 4, 8)

    apply_button = QtWidgets.QPushButton("APPLY")
    apply_button.setFixedHeight(40)

    # Тайловую кнопку удаляем — больше не нужна.
    # Для совместимости оставим атрибут в None, чтобы внешние ссылки не падали.
    main_window.apply_tiled_button = None

    layout.addWidget(apply_button)
    layout.addStretch()

    dock = QtWidgets.QDockWidget("Вычисление", main_window)
    dock.setObjectName("Панель 'Вычисление'")
    dock.setWidget(compute_widget)

    main_window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)

    # Сохраняем ссылку для MainWindow (он сам подпишет on_click)
    main_window.apply_button = apply_button
