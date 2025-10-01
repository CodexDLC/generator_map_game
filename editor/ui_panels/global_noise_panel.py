# ==============================================================================
# Файл: editor/ui_panels/global_noise_panel.py
# ВЕРСИЯ 2.0: Добавлена фабрика make_global_noise_widget для компоновки V2.
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
