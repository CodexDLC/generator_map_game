# ==============================================================================
# Файл: editor/ui_panels/compute_panel.py
# Назначение: Панель запуска вычислений.
#
# ВЕРСИЯ 2.0:
#   - NEW: make_compute_widget(main_window) — фабрика виджета без док-рамки (для V2).
#   - Только одна кнопка "APPLY" (тайловый режим убран). Для совместимости:
#       main_window.apply_tiled_button = None
# ==============================================================================

from __future__ import annotations
from PySide6 import QtWidgets, QtCore


# ------------------------------------------------------------------------------
# V2: фабрика виджета (используется внутри RightOutliner)
def make_compute_widget(main_window) -> QtWidgets.QWidget:
    """
    Создаёт компактный виджет блока COMPUTE с одной кнопкой APPLY.
    Возвращает голый QWidget (без QDockWidget), чтобы его можно было
    встраивать в правую колонку (Outliner) компоновки V2.

    Побочный эффект: кладёт ссылку на кнопку в main_window.apply_button
    и выставляет main_window.apply_tiled_button = None для совместимости.
    """
    root = QtWidgets.QWidget()
    root.setObjectName("ComputeWidget")

    lay = QtWidgets.QVBoxLayout(root)
    lay.setContentsMargins(4, 8, 4, 8)
    lay.setSpacing(6)

    # Заголовок (по желанию — можно убрать, если лишний)
    title = QtWidgets.QLabel("Compute")
    title.setStyleSheet("font-weight: bold;")
    lay.addWidget(title)

    # Кнопка APPLY
    apply_button = QtWidgets.QPushButton("APPLY")
    apply_button.setObjectName("apply_button_right_outliner")
    apply_button.setFixedHeight(40)

    # Совместимость: тайловую кнопку больше не поддерживаем
    try:
        main_window.apply_tiled_button = None
    except Exception:
        pass

    # Сохраняем «главную» кнопку запуска в main_window (как и раньше)
    try:
        main_window.apply_button = apply_button
    except Exception:
        pass

    lay.addWidget(apply_button)
    lay.addStretch(1)
    return root
