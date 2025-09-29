# ==============================================================================
# Файл: editor/ui_panels/global_noise_panel.py
# ВЕРСИЯ 2.0: Добавлена фабрика make_global_noise_widget для компоновки V2.
#             Функция create_global_noise_dock оставлена для совместимости (V1).
# ==============================================================================

from PySide6 import QtWidgets, QtCore


def make_global_noise_widget(main_window) -> QtWidgets.QWidget:
    """
    (V2 NEW) Создаёт и возвращает виджет с параметрами «Глобальный Шум»
    для встраивания в любой лэйаут/сплиттер (без док-обёртки).
    Все контролы привязываются к полям main_window.* как и раньше.
    """
    noise_widget = QtWidgets.QWidget()
    noise_widget.setObjectName("GlobalNoiseWidget")
    form_layout = QtWidgets.QFormLayout(noise_widget)
    form_layout.setContentsMargins(6, 6, 6, 6)
    form_layout.setSpacing(6)

    # Scale
    main_window.gn_scale_input = QtWidgets.QDoubleSpinBox()
    main_window.gn_scale_input.setRange(1.0, 99999.0)
    main_window.gn_scale_input.setDecimals(1)
    main_window.gn_scale_input.setValue(6000.0)
    main_window.gn_scale_input.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
    form_layout.addRow("Scale (tiles):", main_window.gn_scale_input)

    # Octaves
    main_window.gn_octaves_input = QtWidgets.QSpinBox()
    main_window.gn_octaves_input.setRange(1, 16)
    main_window.gn_octaves_input.setValue(3)
    main_window.gn_octaves_input.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
    form_layout.addRow("Octaves:", main_window.gn_octaves_input)

    # Amplitude
    main_window.gn_amp_input = QtWidgets.QDoubleSpinBox()
    main_window.gn_amp_input.setRange(0.0, 9999.0)
    main_window.gn_amp_input.setDecimals(1)
    main_window.gn_amp_input.setValue(400.0)
    main_window.gn_amp_input.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
    form_layout.addRow("Amplitude (m):", main_window.gn_amp_input)

    # Ridge
    main_window.gn_ridge_checkbox = QtWidgets.QCheckBox()
    form_layout.addRow("Ridge:", main_window.gn_ridge_checkbox)

    return noise_widget


def create_global_noise_dock(main_window) -> None:
    """
    (V1 LEGACY) Создаёт док-виджет «Глобальный Шум».
    Внутри использует ту же разметку, что и V2-фабрика.
    """
    noise_widget = make_global_noise_widget(main_window)

    dock = QtWidgets.QDockWidget("Глобальный Шум", main_window)
    dock.setObjectName("Панель 'Глобальный Шум'")
    dock.setWidget(noise_widget)

    main_window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)
    main_window.dock_global_noise = dock
