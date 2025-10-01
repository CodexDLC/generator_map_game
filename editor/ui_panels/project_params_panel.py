# ==============================================================================
# Файл: editor/ui_panels/project_params_panel.py
# Назначение: Панель «Параметры Проекта»
#
# ВЕРСИЯ 2.0:
#   - NEW: make_project_params_widget(main_window) — виджет без док-рамки (для V2).
#   - Узкие числовые поля, корректная политика роста формы.
#   - Поля пробрасываются в main_window.* (совместимость с project_binding.py).
# ==============================================================================

from __future__ import annotations
from PySide6 import QtWidgets, QtCore

from editor.utils.system_utils import get_recommended_max_map_size


# ------------------------------------------------------------------------------ helpers

def _spin_int(parent=None, rng=(-999_999, 999_999), step=1, width=110) -> QtWidgets.QSpinBox:
    w = QtWidgets.QSpinBox(parent)
    w.setRange(int(rng[0]), int(rng[1]))
    w.setSingleStep(int(step))
    w.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
    w.setMaximumWidth(int(width))
    return w

def _spin_double(parent=None, rng=(0.0, 1e9), step=0.1, decimals=2, width=110) -> QtWidgets.QDoubleSpinBox:
    w = QtWidgets.QDoubleSpinBox(parent)
    w.setRange(float(rng[0]), float(rng[1]))
    w.setSingleStep(float(step))
    w.setDecimals(int(decimals))
    w.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
    w.setMaximumWidth(int(width))
    return w


# ------------------------------------------------------------------------------ V2 widget factory

def make_project_params_widget(main_window) -> QtWidgets.QWidget:
    """
    Возвращает встраиваемый виджет «Параметры Проекта».
    Все контролы пробрасываются в поля main_window.* (см. project_binding.py).
    """
    root = QtWidgets.QWidget()
    root.setObjectName("ProjectParamsWidget")

    form = QtWidgets.QFormLayout(root)
    form.setContentsMargins(8, 8, 8, 8)
    form.setSpacing(6)
    form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
    form.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)

    # --- Поля проекта (совместимы с project_binding.apply_project_to_ui/collect)

    # seed
    main_window.seed_input = _spin_int(root, rng=(0, 999_999), step=1)
    main_window.seed_input.setObjectName("seed_input")
    form.addRow("World Seed:", main_window.seed_input)

    # глобальные смещения
    main_window.global_x_offset_input = _spin_int(root, rng=(-999_999, 999_999), step=512)
    main_window.global_x_offset_input.setObjectName("global_x_offset_input")
    form.addRow("Global X Offset:", main_window.global_x_offset_input)

    main_window.global_z_offset_input = _spin_int(root, rng=(-999_999, 999_999), step=512)
    main_window.global_z_offset_input.setObjectName("global_z_offset_input")
    form.addRow("Global Z Offset:", main_window.global_z_offset_input)

    # размеры тайла/региона
    main_window.chunk_size_input = _spin_int(root, rng=(16, 2048), step=16)
    main_window.chunk_size_input.setObjectName("chunk_size_input")
    form.addRow("Chunk Size (px):", main_window.chunk_size_input)

    main_window.region_size_input = _spin_int(root, rng=(1, 64), step=1)
    main_window.region_size_input.setObjectName("region_size_input")
    form.addRow("Region Size (chunks):", main_window.region_size_input)

    # размер клетки (м/px)
    main_window.cell_size_input = _spin_double(root, rng=(0.01, 1000.0), step=0.01, decimals=2)
    main_window.cell_size_input.setObjectName("cell_size_input")
    form.addRow("Cell Size (m/px):", main_window.cell_size_input)

    # итоговый размер мира (подсказка)
    info_lay = QtWidgets.QHBoxLayout()
    main_window.total_size_label = QtWidgets.QLabel("—")
    main_window.total_size_label.setObjectName("total_size_label")
    info_lay.addWidget(QtWidgets.QLabel("Total world size:"))
    info_lay.addWidget(main_window.total_size_label, 1)
    form.addRow(info_lay)

    # значения по умолчанию
    main_window.seed_input.setValue(1)
    main_window.global_x_offset_input.setValue(0)
    main_window.global_z_offset_input.setValue(0)
    main_window.chunk_size_input.setValue(128)
    main_window.region_size_input.setValue(4)
    main_window.cell_size_input.setValue(1.0)

    # обновление подсказки о размере
    def update_total_size():
        cs = int(main_window.chunk_size_input.value())
        rs = int(main_window.region_size_input.value())
        px = cs * rs
        text = f"{px} × {px} px per region"
        # рекомендация по max size (если доступна)
        try:
            rec = get_recommended_max_map_size()
            if isinstance(rec, int) and px > rec:
                text += f"   (⚠ рекомендуемый максимум: {rec})"
                main_window.total_size_label.setStyleSheet("color: #ffcc00; font-weight: bold;")
            else:
                main_window.total_size_label.setStyleSheet("color: #aaa;")
        except Exception:
            main_window.total_size_label.setStyleSheet("color: #aaa;")
        main_window.total_size_label.setText(text)

    main_window.chunk_size_input.valueChanged.connect(update_total_size)
    main_window.region_size_input.valueChanged.connect(update_total_size)
    update_total_size()

    # растяжка вниз
    form.addItem(QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding))
    return root
