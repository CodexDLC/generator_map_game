# editor/core/main_window.py
from __future__ import annotations
import logging
import traceback
from typing import Optional, Dict, Any
from dataclasses import asdict
import json
import math

import numpy as np
from PySide6 import QtWidgets, QtCore, QtGui

# --- Импорты ---
from editor.graph.graph_runner import run_graph
from editor.logic import planet_view_logic
from editor.ui.layouts.properties_panel import create_properties_widget
from editor.ui.widgets.custom_controls import SliderSpinCombo, SeedWidget, CollapsibleBox
from editor.ui.layouts.central_layout import create_bottom_work_area_v2
from editor.ui.layouts.main_menu import build_menus
from editor.ui.layouts.node_inspector_panel import make_node_inspector_widget
from editor.ui.layouts.presets_panel import make_region_presets_widget
from editor.ui.bindings.shortcuts import install_shortcuts
from editor.ui.widgets.preview_widget import Preview3DWidget
from editor.ui.layouts.world_settings_panel import make_world_settings_widget, MAX_SIDE_METERS
from editor.ui.layouts.render_panel import make_render_panel_widget
from editor.core.render_settings import RenderSettings
from editor.render.sphere_preview_widget import SpherePreviewWidget
# --- ИЗМЕНЕНИЕ: Добавляем недостающие импорты ---

from editor.core.project_manager import ProjectManager
from editor.actions import preset_actions

logger = logging.getLogger(__name__)



class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs) -> None:
        project_path: Optional[str] = kwargs.pop("project_path", None)
        super().__init__(*args, **kwargs)

        self.setWindowTitle("Редактор Миров")
        self.resize(1600, 900)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.project_manager = ProjectManager(self)
        self.render_settings = RenderSettings()

        # --- Инициализация всех атрибутов UI ---
        self.graph: 'CustomNodeGraph' | None = None
        self.preview_widget: Preview3DWidget | None = None
        self.planet_widget: SpherePreviewWidget | None = None
        self.central_tabs: QtWidgets.QTabWidget | None = None
        self.props_bin: QtWidgets.QWidget | None = None
        self.right_outliner: 'RightOutlinerWidget' | None = None
        self.left_palette: QtWidgets.QWidget | None = None
        self.node_inspector: QtWidgets.QWidget | None = None
        self.presets_widget: 'RegionPresetsWidget' | None = None
        self.render_panel: QtWidgets.QWidget | None = None
        self.realtime_checkbox: QtWidgets.QCheckBox | None = None

        # Атрибуты из world_settings_panel
        self.subdivision_level_input: QtWidgets.QComboBox | None = None
        self.region_resolution_input: QtWidgets.QComboBox | None = None
        self.vertex_distance_input: QtWidgets.QDoubleSpinBox | None = None
        self.max_height_input: QtWidgets.QDoubleSpinBox | None = None
        self.planet_radius_label: QtWidgets.QLabel | None = None
        self.base_elevation_label: QtWidgets.QLabel | None = None
        self.ws_noise_box: CollapsibleBox | None = None
        self.ws_sea_level: SliderSpinCombo | None = None
        self.ws_relative_scale: SliderSpinCombo | None = None
        self.ws_sphere_octaves: SliderSpinCombo | None = None
        self.ws_sphere_gain: SliderSpinCombo | None = None
        self.ws_sphere_ridge: QtWidgets.QCheckBox | None = None
        self.ws_sphere_seed: SeedWidget | None = None

        self.update_planet_btn: QtWidgets.QPushButton | None = None

        self.current_world_offset = (0.0, 0.0)
        self._last_selected_node = None

        self._build_ui()
        build_menus(self)
        install_shortcuts(self)
        if project_path:
            self.project_manager.load_project(project_path)
        self._load_app_settings()

    def _build_ui(self) -> None:
        try:
            self.preview_widget = Preview3DWidget(self)
            self.preview_widget.setParent(self)
        except (ImportError, RuntimeError) as e:
            logger.exception(f"Не удалось создать Preview3DWidget: {e}")
            self.preview_widget = QtWidgets.QLabel("Preview widget failed to load")
            self.preview_widget.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.planet_widget = SpherePreviewWidget(self)

        planet_container = QtWidgets.QWidget()
        planet_layout = QtWidgets.QVBoxLayout(planet_container)
        planet_layout.setContentsMargins(0, 0, 0, 0)
        planet_layout.setSpacing(6)
        planet_layout.addWidget(self.planet_widget, 1)

        planet_bottom_bar = QtWidgets.QHBoxLayout()
        planet_bottom_bar.setContentsMargins(8, 0, 8, 8)
        planet_bottom_bar.addStretch()
        self.update_planet_btn = QtWidgets.QPushButton("Обновить Планету")
        planet_bottom_bar.addWidget(self.update_planet_btn)
        planet_layout.addLayout(planet_bottom_bar)

        self.central_tabs = QtWidgets.QTabWidget()
        self.central_tabs.addTab(self.preview_widget, "3D Превью")
        self.central_tabs.addTab(planet_container, "Планета")

        bottom_work_area, self.graph, self.left_palette, self.right_outliner = create_bottom_work_area_v2(self)
        tabs_left = self._create_left_tabs()
        tabs_right = self._create_right_tabs()

        top_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal, self)
        top_splitter.addWidget(tabs_left)
        top_splitter.addWidget(self.central_tabs)
        top_splitter.addWidget(tabs_right)
        top_splitter.setStretchFactor(1, 1)
        top_splitter.setSizes([360, 900, 420])

        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical, self)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(bottom_work_area)
        main_splitter.setSizes([int(self.height() * 0.55), int(self.height() * 0.45)])
        self.setCentralWidget(main_splitter)
        self._connect_components()

    def _create_left_tabs(self) -> QtWidgets.QTabWidget:
        tabs = QtWidgets.QTabWidget()
        tabs.setDocumentMode(True)
        world_settings_panel, ws_widgets = make_world_settings_widget(self)

        for name, widget in ws_widgets.items():
            setattr(self, name, widget)

        tabs.addTab(world_settings_panel, "Настройки Мира")
        self.presets_widget = make_region_presets_widget(self)
        tabs.addTab(self.presets_widget, "Пресеты")
        return tabs

    def _create_right_tabs(self) -> QtWidgets.QTabWidget:
        tabs = QtWidgets.QTabWidget()
        tabs.setObjectName("TopTabsRight")
        tabs.setDocumentMode(True)
        self.props_bin = create_properties_widget(self)
        tabs.addTab(self.props_bin, "Параметры")
        self.node_inspector = make_node_inspector_widget(self)
        tabs.addTab(self.node_inspector, "Инспектор")
        self.render_panel = make_render_panel_widget(self, self.render_settings, self._on_render_settings_changed)
        tabs.addTab(self.render_panel, "Рендер")
        return tabs

    def _connect_components(self):
        if self.region_resolution_input: self.region_resolution_input.currentIndexChanged.connect(
            self._update_dynamic_ranges)
        if self.vertex_distance_input: self.vertex_distance_input.valueChanged.connect(self._update_calculated_fields)

        # --- ИЗМЕНЕНИЕ: Добавляем вызов _update_planet_view при смене уровня подразделения ---
        if self.subdivision_level_input:
            self.subdivision_level_input.currentIndexChanged.connect(self._update_calculated_fields)
            self.subdivision_level_input.currentIndexChanged.connect(self._update_planet_view)

        # Подключаем сигналы для обновления планеты
        if self.update_planet_btn: self.update_planet_btn.clicked.connect(self._update_planet_view)
        if self.ws_sea_level: self.ws_sea_level.editingFinished.connect(self._update_planet_view)
        if self.ws_relative_scale: self.ws_relative_scale.editingFinished.connect(self._update_planet_view)
        if self.ws_sphere_octaves: self.ws_sphere_octaves.editingFinished.connect(self._update_planet_view)
        if self.ws_sphere_gain: self.ws_sphere_gain.editingFinished.connect(self._update_planet_view)
        if self.ws_sphere_ridge: self.ws_sphere_ridge.toggled.connect(self._update_planet_view)
        if self.ws_sphere_seed: self.ws_sphere_seed.editingFinished.connect(self._update_planet_view)

        if self.graph:
            if self.props_bin: self.props_bin.set_graph(self.graph, self)
            if self.node_inspector: self.node_inspector.bind_graph(self.graph)
            if self.right_outliner: self.right_outliner.bind_graph(self.graph)
            if self.left_palette: self.left_palette.bind_graph(self.graph)
            QtCore.QTimer.singleShot(0, self.graph.finalize_setup)
            self.graph.selection_changed.connect(self._on_node_selection_changed)
        if self.right_outliner: self.right_outliner.apply_clicked.connect(self._on_apply_clicked)
        if self.presets_widget:
            self.presets_widget.load_requested.connect(self.action_load_region_preset)
            self.presets_widget.create_from_current_requested.connect(self.action_create_preset_from_dialog)
            self.presets_widget.delete_requested.connect(self.action_delete_preset_by_name)
            self.presets_widget.save_as_requested.connect(self.action_save_active_preset)

        QtCore.QTimer.singleShot(0, self._update_dynamic_ranges)

    def _update_dynamic_ranges(self):
        if not (self.region_resolution_input and self.vertex_distance_input): return
        res_str = self.region_resolution_input.currentText()
        resolution = int(res_str.split('x')[0])
        max_dist = MAX_SIDE_METERS / resolution
        self.vertex_distance_input.blockSignals(True)
        self.vertex_distance_input.setRange(0.25, max_dist)
        if self.vertex_distance_input.value() > max_dist:
            self.vertex_distance_input.setValue(max_dist)
        self.vertex_distance_input.blockSignals(False)
        self._update_calculated_fields()

    def _update_calculated_fields(self):
        if not all([self.subdivision_level_input, self.region_resolution_input, self.vertex_distance_input,
                    self.planet_radius_label, self.base_elevation_label, self.max_height_input]): return
        try:
            # Расчет радиуса планеты (без изменений)
            res_str = self.region_resolution_input.currentText()
            resolution = int(res_str.split('x')[0])
            dist = self.vertex_distance_input.value()
            region_side_m = resolution * dist
            hex_area_m2 = (region_side_m ** 2) * (math.sqrt(3) / 2)
            subdiv_text = self.subdivision_level_input.currentText()
            num_regions = int(subdiv_text.split(" ")[1].strip("()регинов"))
            total_surface_area_m2 = num_regions * hex_area_m2
            radius_m = math.sqrt(total_surface_area_m2 / (4 * math.pi))
            radius_km = radius_m / 1000.0
            self.planet_radius_label.setText(f"{radius_km:,.0f} км")

            # --- ИСПРАВЛЕННАЯ ЛОГИКА РАСЧЕТА ---
            # Базовый перепад высот теперь - это 30% от Максимальной высоты.
            # Это дает интуитивно понятную связь между параметрами.
            max_h = self.max_height_input.value()
            base_elevation = max_h * 0.3
            self.base_elevation_label.setText(f"{base_elevation:,.0f} м")

        except Exception as e:
            logger.error(f"Ошибка при расчете полей: {e}")
            self.planet_radius_label.setText("Ошибка")
            self.base_elevation_label.setText("Ошибка")

    @QtCore.Slot(object)
    def _on_render_settings_changed(self, new_settings: RenderSettings):
        old_hex = self.render_settings.height_exaggeration
        new_hex = new_settings.height_exaggeration
        self.render_settings = new_settings
        if self.preview_widget:
            self.preview_widget.apply_render_settings(new_settings)
        if abs(old_hex - new_hex) > 1e-6:
            self._on_apply_clicked()

    @QtCore.Slot()
    def _trigger_preview_update(self):
        if self.realtime_checkbox and self.realtime_checkbox.isChecked():
            self._on_apply_clicked()

    @QtCore.Slot(list)
    def _on_node_selection_changed(self, selected_nodes):
        if selected_nodes:
            self._last_selected_node = selected_nodes[0]
            if self.realtime_checkbox and self.realtime_checkbox.isChecked():
                self._on_apply_clicked()

    def get_project_data(self) -> Dict[str, Any] | None:
        return self.project_manager.current_project_data

    def get_active_graph(self):
        return self.graph

    def new_project(self):
        self.project_manager.new_project()

    def open_project(self):
        self.project_manager.open_project()

    def save_project(self) -> bool:
        return self.project_manager.save_project()

    def _load_presets_list(self):
        if not self.presets_widget or not self.project_manager.current_project_data: return
        presets_data = self.project_manager.current_project_data.get("region_presets", {})
        self.presets_widget.set_presets(list(presets_data.keys()))
        active_preset = self.project_manager.current_project_data.get("active_preset_name")
        if active_preset: self.presets_widget.select_preset(active_preset)

    def action_load_region_preset(self, preset_name: str):
        project_data = self.get_project_data()
        if not project_data: return
        preset_info = project_data.get("region_presets", {}).get(preset_name)
        if preset_info:
            project_data["active_preset_name"] = preset_name
            preset_actions.load_preset_into_graph(self, preset_info)
            if self.presets_widget:
                self.presets_widget.select_preset(preset_name)
            self._mark_dirty()

    def action_create_preset_from_dialog(self, _preset_name_from_field: str):
        preset_actions.handle_new_preset(self)

    def action_delete_preset_by_name(self, preset_name: str):
        if self.presets_widget:
            items = self.presets_widget.list.findItems(preset_name, QtCore.Qt.MatchFlag.MatchExactly)
            if items:
                self.presets_widget.list.setCurrentItem(items[0])
                preset_actions.handle_delete_preset(self)

    def action_save_active_preset(self):
        preset_actions.handle_save_active_preset(self)

    def _mark_dirty(self, *_args, **_kwargs):
        self.project_manager.mark_dirty(True)

    def closeEvent(self, ev: QtGui.QCloseEvent):
        self._save_app_settings()
        if self.project_manager.close_project_with_confirmation():
            ev.accept()
        else:
            ev.ignore()

    def _on_apply_clicked(self):
        if self.right_outliner: self.right_outliner.set_busy(True)
        try:
            target_node = self.graph.selected_nodes()[
                0] if self.graph and self.graph.selected_nodes() else self._last_selected_node
            if not target_node:
                logger.warning("Нет выбранной ноды для превью. Рендер отменен.")
                return
            logger.info(f"Рендеринг превью для ноды: '{target_node.name()}'")
            context = self.project_manager.collect_ui_context(for_preview=True)
            context["world_input_noise"] = np.zeros_like(context["x_coords"], dtype=np.float32)
            final_map_01 = run_graph(target_node, context)
            preview_max_height = context.get('max_height_m', 1000.0)
            final_map_meters = final_map_01 * preview_max_height
            if self.preview_widget:
                self.preview_widget.update_mesh(final_map_meters, 1.0)
        except Exception as e:
            logger.exception(f"Ошибка во время генерации: {e}")
            QtWidgets.QMessageBox.critical(self, "Ошибка генерации",
                                           f"Произошла ошибка: {e}\n\n{traceback.format_exc()}")
        finally:
            if self.right_outliner: self.right_outliner.set_busy(False)

    def _trigger_apply(self) -> None:
        if self.right_outliner and self.right_outliner.apply_button:
            self.right_outliner.apply_button.animateClick(10)

    # --- ИЗМЕНЕНИЕ: Новый метод для открытия вкладки "Планета" ---
    def show_planet_view(self):
        if self.central_tabs:
            for i in range(self.central_tabs.count()):
                if self.central_tabs.tabText(i) == "Планета":
                    self.central_tabs.setCurrentIndex(i)
                    # Если виджет еще не был отрисован, запускаем обновление
                    if self.planet_widget and self.planet_widget._vbo is None:
                        self._update_planet_view()
                    break

    @QtCore.Slot()
    def _update_planet_view(self):
        if self.update_planet_btn: self.update_planet_btn.setEnabled(False)
        QtWidgets.QApplication.processEvents()

        try:
            # 1. Собираем АКТУАЛЬНЫЕ настройки из UI в словарь
            world_settings = {
                'subdivision_level': int(self.subdivision_level_input.currentText().split(" ")[0]),
                'disp_scale': 0.05,
                # --- ИСПРАВЛЕНИЕ: Считываем значение с каждого виджета ---
                'sea_level': self.ws_sea_level.value(),
                'sphere_params': {
                    'octaves': int(self.ws_sphere_octaves.value()),
                    'gain': self.ws_sphere_gain.value(),
                    'ridge': self.ws_sphere_ridge.isChecked(),
                    'seed': self.ws_sphere_seed.value(),
                    'frequency': 1.0 / (self.ws_relative_scale.value() * 4.0)
                }
            }

            # 2. Передаем собранные настройки в модуль логики
            planet_view_logic.update_planet_widget(self.planet_widget, world_settings)

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Ошибка", f"Не удалось обновить 3D-планету: {e}")
        finally:
            if self.update_planet_btn: self.update_planet_btn.setEnabled(True)

    def _load_app_settings(self):
        settings = QtCore.QSettings("WorldForge", "Editor")
        render_data_str = settings.value("render_settings")
        if render_data_str and isinstance(render_data_str, str):
            try:
                render_data = json.loads(render_data_str)
                self.render_settings = RenderSettings.from_dict(render_data)
                if self.render_panel:
                    self.render_panel.set_settings(self.render_settings)
                logger.info("Настройки рендера успешно загружены.")
            except Exception as e:
                logger.error(f"Не удалось загрузить настройки рендера: {e}")

    def _save_app_settings(self):
        settings = QtCore.QSettings("WorldForge", "Editor")
        try:
            render_data = asdict(self.render_settings)
            settings.setValue("render_settings", json.dumps(render_data))
            logger.info("Настройки рендера сохранены.")
        except Exception as e:
            logger.error(f"Не удалось сохранить настройки рендера: {e}")