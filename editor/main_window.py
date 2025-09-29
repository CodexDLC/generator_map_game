# ==============================================================================
# Файл: main_window.py
# ВЕРСИЯ 4.3 (РЕФАКТОРИНГ): Разделены панели параметров.
# - Настройки глобального шума вынесены на свою собственную вкладку.
# ==============================================================================

from __future__ import annotations

import logging
from typing import Optional

from PySide6 import QtWidgets, QtCore, QtGui

from editor.theme import APP_STYLE_SHEET
from editor.ui_panels.central_graph import create_bottom_work_area_v2
from editor.ui_panels.menu import build_menus
from editor.ui_panels.properties_panel import make_properties_widget
from editor.ui_panels.shortcuts import install_shortcuts
from editor.preview_widget import Preview3DWidget
from editor.project_manager import ProjectManager

logger = logging.getLogger(__name__)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs) -> None:
        project_path: Optional[str] = kwargs.pop("project_path", None)
        super().__init__(*args, **kwargs)

        self.setWindowTitle("Редактор Миров")
        self.resize(1600, 900)

        self.project_manager = ProjectManager(self)

        # --- UI-компоненты ---
        self.graph = None
        self.preview_widget = None
        self.props_bin = None
        self.right_outliner = None
        self.left_palette = None

        # --- Виджеты параметров ---
        self.seed_input: QtWidgets.QSpinBox | None = None
        self.chunk_size_input: QtWidgets.QSpinBox | None = None
        self.region_size_in_chunks_input: QtWidgets.QSpinBox | None = None
        self.cell_size_input: QtWidgets.QDoubleSpinBox | None = None
        self.global_x_offset_input: QtWidgets.QDoubleSpinBox | None = None
        self.global_z_offset_input: QtWidgets.QDoubleSpinBox | None = None
        self.gn_scale_input: QtWidgets.QDoubleSpinBox | None = None
        self.gn_octaves_input: QtWidgets.QSpinBox | None = None
        self.gn_amp_input: QtWidgets.QDoubleSpinBox | None = None
        self.gn_ridge_checkbox: QtWidgets.QCheckBox | None = None

        self._build_ui()

        build_menus(self)
        install_shortcuts(self)

        if project_path:
            self.project_manager.load_project(project_path)

    def _build_ui(self) -> None:
        try:
            self.preview_widget = Preview3DWidget(self)
        except Exception as e:
            logger.exception(f"Не удалось создать Preview3DWidget: {e}")
            lbl = QtWidgets.QLabel("Preview widget failed to load")
            lbl.setAlignment(QtCore.Qt.AlignCenter)
            self.preview_widget = lbl

        bottom_work_area, self.graph, self.left_palette, self.right_outliner = create_bottom_work_area_v2(self)

        tabs_left = self._create_left_tabs()
        tabs_right = self._create_right_tabs()

        top_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        top_splitter.addWidget(tabs_left)
        top_splitter.addWidget(self.preview_widget)
        top_splitter.addWidget(tabs_right)
        top_splitter.setStretchFactor(1, 1)
        top_splitter.setSizes([360, 900, 420])

        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical, self)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(bottom_work_area)
        main_splitter.setSizes([int(self.height() * 0.55), int(self.height() * 0.45)])

        self.setCentralWidget(main_splitter)
        self._connect_components()

    def _create_project_params_panel(self) -> QtWidgets.QWidget:
        """Создает панель с основными параметрами проекта."""
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.seed_input = QtWidgets.QSpinBox()
        self.seed_input.setRange(0, 999999999)
        layout.addRow("Seed:", self.seed_input)

        self.chunk_size_input = QtWidgets.QSpinBox()
        self.chunk_size_input.setRange(16, 2048)
        self.chunk_size_input.setSingleStep(16)
        layout.addRow("Размер чанка:", self.chunk_size_input)

        self.region_size_in_chunks_input = QtWidgets.QSpinBox()
        self.region_size_in_chunks_input.setRange(1, 16)
        layout.addRow("Регион (в чанках):", self.region_size_in_chunks_input)

        self.cell_size_input = QtWidgets.QDoubleSpinBox()
        self.cell_size_input.setRange(0.1, 10.0)
        self.cell_size_input.setSingleStep(0.1)
        self.cell_size_input.setDecimals(1)
        layout.addRow("Размер ячейки:", self.cell_size_input)

        self.global_x_offset_input = QtWidgets.QDoubleSpinBox()
        self.global_x_offset_input.setRange(-1000000.0, 1000000.0)
        layout.addRow("Смещение X:", self.global_x_offset_input)

        self.global_z_offset_input = QtWidgets.QDoubleSpinBox()
        self.global_z_offset_input.setRange(-1000000.0, 1000000.0)
        layout.addRow("Смещение Z:", self.global_z_offset_input)

        layout.addItem(QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding))
        return panel

    def _create_global_noise_panel(self) -> QtWidgets.QWidget:
        """Создает панель с параметрами глобального шума."""
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.gn_scale_input = QtWidgets.QDoubleSpinBox()
        self.gn_scale_input.setRange(1.0, 100000.0)
        self.gn_scale_input.setSingleStep(100.0)
        layout.addRow("Масштаб:", self.gn_scale_input)

        self.gn_octaves_input = QtWidgets.QSpinBox()
        self.gn_octaves_input.setRange(1, 10)
        layout.addRow("Октавы:", self.gn_octaves_input)

        self.gn_amp_input = QtWidgets.QDoubleSpinBox()
        self.gn_amp_input.setRange(0.0, 1000.0)
        layout.addRow("Амплитуда (м):", self.gn_amp_input)

        self.gn_ridge_checkbox = QtWidgets.QCheckBox()
        layout.addRow("Ridge:", self.gn_ridge_checkbox)

        layout.addItem(QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding))
        return panel

    def _create_left_tabs(self) -> QtWidgets.QTabWidget:
        tabs = QtWidgets.QTabWidget()
        tabs.setDocumentMode(True)
        
        project_params_panel = self._create_project_params_panel()
        tabs.addTab(project_params_panel, "Параметры Проекта")

        global_noise_panel = self._create_global_noise_panel()
        tabs.addTab(global_noise_panel, "Глобальный Шум")
        
        return tabs

    def _create_right_tabs(self) -> QtWidgets.QTabWidget:
        tabs = QtWidgets.QTabWidget()
        tabs.setDocumentMode(True)
        self.props_bin = make_properties_widget(self)
        tabs.addTab(self.props_bin, "Параметры")
        tabs.addTab(QtWidgets.QWidget(), "Нода")
        return tabs

    def _connect_components(self):
        if self.graph:
            if self.props_bin: self.props_bin.set_graph(self.graph)
            if self.right_outliner: self.right_outliner.bind_graph(self.graph)
            if self.left_palette: self.left_palette.bind_graph(self.graph)

            self.graph.finalize_setup()
            
            self.graph.structure_changed.connect(self._mark_dirty)
            self.graph.property_changed.connect(self._mark_dirty)

        # Подключаем все виджеты к _mark_dirty
        for widget in [self.seed_input, self.chunk_size_input, self.region_size_in_chunks_input, 
                       self.cell_size_input, self.global_x_offset_input, self.global_z_offset_input, 
                       self.gn_scale_input, self.gn_octaves_input, self.gn_amp_input]:
            if widget and isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
                widget.valueChanged.connect(self._mark_dirty)
        
        if self.gn_ridge_checkbox:
            self.gn_ridge_checkbox.toggled.connect(self._mark_dirty)

        if self.right_outliner:
            self.right_outliner.apply_clicked.connect(self._on_apply_clicked)

    def new_project(self):
        self.project_manager.new_project()

    def open_project(self):
        self.project_manager.open_project()

    def save_project(self) -> bool:
        return self.project_manager.save_project()

    def _mark_dirty(self, *args, **kwargs):
        self.project_manager.mark_dirty(True)

    def closeEvent(self, ev: QtGui.QCloseEvent):
        if self.project_manager.close_project_with_confirmation():
            ev.accept()
        else:
            ev.ignore()

    def _on_apply_clicked(self):
        pass

    def _trigger_apply(self) -> None:
        if self.right_outliner and self.right_outliner.apply_button:
            self.right_outliner.apply_button.animateClick(10)
