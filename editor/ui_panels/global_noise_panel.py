# ==============================================================================
# Файл: editor/ui_panels/global_noise_panel.py
# Назначение: Модуль для создания панели "Глобальный Шум".
# ВЕРСИЯ 1.2: Добавлен objectName.
# ==============================================================================
from PySide6 import QtWidgets, QtCore


def create_global_noise_dock(main_window) -> None:
    """
    Создает и настраивает док-виджет с параметрами глобального шума.
    """
    noise_widget = QtWidgets.QWidget()
    form_layout = QtWidgets.QFormLayout(noise_widget)

    main_window.gn_scale_input = QtWidgets.QDoubleSpinBox()
    main_window.gn_scale_input.setRange(1.0, 99999.0)
    main_window.gn_scale_input.setDecimals(1)
    main_window.gn_scale_input.setValue(6000.0)
    form_layout.addRow("Scale (tiles):", main_window.gn_scale_input)

    main_window.gn_octaves_input = QtWidgets.QSpinBox()
    main_window.gn_octaves_input.setRange(1, 16)
    main_window.gn_octaves_input.setValue(3)
    form_layout.addRow("Octaves:", main_window.gn_octaves_input)

    main_window.gn_amp_input = QtWidgets.QDoubleSpinBox()
    main_window.gn_amp_input.setRange(0.0, 9999.0)
    main_window.gn_amp_input.setDecimals(1)
    main_window.gn_amp_input.setValue(400.0)
    form_layout.addRow("Amplitude (m):", main_window.gn_amp_input)

    main_window.gn_ridge_checkbox = QtWidgets.QCheckBox()
    form_layout.addRow("Ridge:", main_window.gn_ridge_checkbox)

    dock = QtWidgets.QDockWidget("Глобальный Шум", main_window)
    dock.setObjectName("Панель 'Глобальный Шум'")
    dock.setWidget(noise_widget)

    main_window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)

    main_window.dock_global_noise = dock
