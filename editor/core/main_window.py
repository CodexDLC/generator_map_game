# editor/core/main_window.py
from __future__ import annotations
import logging
import traceback
from typing import Optional, Dict, Any
from dataclasses import asdict
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PySide6 import QtWidgets, QtCore, QtGui

from editor.actions.project_actions import on_save_project
from editor.graph.custom_graph import CustomNodeGraph
from editor.ui.layouts.right_outliner_panel import RightOutlinerWidget

logger = logging.getLogger(__name__)

from editor.logic.background_workers import PlanetGenerationWorker, PreviewGenerationWorker
from editor.ui.layouts.properties_panel import create_properties_widget
from editor.ui.widgets.custom_controls import SliderSpinCombo, SeedWidget, CollapsibleBox
from editor.ui.layouts.central_layout import create_bottom_work_area_v2
from editor.ui.layouts.main_menu import build_menus
from editor.ui.layouts.node_inspector_panel import make_node_inspector_widget
from editor.ui.layouts.presets_panel import make_region_presets_widget, RegionPresetsWidget
from editor.ui.bindings.shortcuts import install_shortcuts
from editor.ui.widgets.preview_widget import Preview3DWidget
from editor.ui.layouts.world_settings_panel import make_world_settings_widget, MAX_SIDE_METERS, PLANET_ROUGHNESS_PRESETS
from editor.ui.layouts.render_panel import make_render_panel_widget
from editor.core.render_settings import RenderSettings
from editor.render.sphere_preview_widget import SpherePreviewWidget
from editor.core.project_manager import ProjectManager
from editor.actions import preset_actions, export_actions


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs) -> None:
        project_path: Optional[str] = kwargs.pop("project_path", None)
        super().__init__(*args, **kwargs)

        self.setWindowTitle("Редактор Миров")
        self.resize(1600, 900)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.project_manager = ProjectManager(self)
        self.render_settings = RenderSettings()

        self.thread_pool = QtCore.QThreadPool()
        logger.info(f"Создан пул потоков с {self.thread_pool.maxThreadCount()} потоками.")

        # --- ОБЪЯВЛЕНИЕ АТРИБУТОВ КЛАССА ---
        self.graph: Optional['CustomNodeGraph'] = None
        self.preview_widget: Optional[Preview3DWidget] = None
        self.planet_widget: Optional[SpherePreviewWidget] = None
        self.loading_overlay: Optional[QtWidgets.QWidget] = None
        self.central_tabs: Optional[QtWidgets.QTabWidget] = None
        self.props_bin: Optional[QtWidgets.QWidget] = None
        self.right_outliner: Optional['RightOutlinerWidget'] = None
        self.left_palette: Optional[QtWidgets.QWidget] = None
        self.node_inspector: Optional[QtWidgets.QWidget] = None
        self.presets_widget: Optional['RegionPresetsWidget'] = None
        self.render_panel: Optional[QtWidgets.QWidget] = None
        self.realtime_checkbox: Optional[QtWidgets.QCheckBox] = None

        # --- Атрибуты для настроек мира ---
        self.subdivision_level_input: Optional[QtWidgets.QComboBox] = None
        self.planet_preview_detail_input: Optional[QtWidgets.QComboBox] = None
        self.region_resolution_input: Optional[QtWidgets.QComboBox] = None
        self.vertex_distance_input: Optional[QtWidgets.QDoubleSpinBox] = None
        self.max_height_input: Optional[QtWidgets.QDoubleSpinBox] = None
        self.planet_radius_label: Optional[QtWidgets.QLabel] = None
        self.base_elevation_label: Optional[QtWidgets.QLabel] = None
        self.ws_noise_box: Optional[CollapsibleBox] = None
        self.planet_type_preset_input: Optional[QtWidgets.QComboBox] = None
        self.ws_sea_level: Optional[SliderSpinCombo] = None
        self.ws_relative_scale: Optional[SliderSpinCombo] = None
        self.ws_octaves: Optional[SliderSpinCombo] = None
        self.ws_gain: Optional[SliderSpinCombo] = None
        self.ws_power: Optional[SliderSpinCombo] = None
        self.ws_warp_strength: Optional[SliderSpinCombo] = None
        self.ws_seed: Optional[SeedWidget] = None
        self.preview_resolution_input: Optional[QtWidgets.QComboBox] = None
        self.region_id_label: Optional[QtWidgets.QLabel] = None
        self.region_center_x_label: Optional[QtWidgets.QLabel] = None
        self.region_center_z_label: Optional[QtWidgets.QLabel] = None
        self.update_planet_btn: Optional[QtWidgets.QPushButton] = None

        # --- НОВЫЕ АТРИБУТЫ ДЛЯ КЛИМАТА ---
        self.climate_enabled: Optional[QtWidgets.QCheckBox] = None
        self.climate_sea_level: Optional[SliderSpinCombo] = None
        self.climate_avg_temp: Optional[SliderSpinCombo] = None
        self.climate_axis_tilt: Optional[SliderSpinCombo] = None
        self.climate_wind_strength: Optional[SliderSpinCombo] = None
        self.biome_probabilities_list: Optional[QtWidgets.QListWidget] = None

        self._last_selected_node = None
        self.current_region_id: int = 0
        self.current_world_offset = (0.0, 0.0, 1.0)

        self._build_ui()
        build_menus(self)
        install_shortcuts(self)
        if project_path:
            self.project_manager.load_project(project_path)
        self._load_app_settings()

        QtCore.QTimer.singleShot(0, self._try_load_planet_from_cache)
        QtCore.QTimer.singleShot(100, lambda: self._on_cell_picked(0))

    def _build_ui(self) -> None:
        try:
            self.preview_widget = Preview3DWidget(self)
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

        self._create_loading_overlay()

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

    def _create_loading_overlay(self):
        self.loading_overlay = QtWidgets.QWidget(self.central_tabs)
        self.loading_overlay.setObjectName("loadingOverlay")
        self.loading_overlay.setStyleSheet("""
            #loadingOverlay {
                background-color: rgba(0, 0, 0, 0.6);
                border-radius: 10px;
            }
        """)
        overlay_layout = QtWidgets.QVBoxLayout(self.loading_overlay)
        overlay_layout.setAlignment(QtCore.Qt.AlignCenter)

        progress = QtWidgets.QProgressBar()
        progress.setRange(0, 0)
        progress.setTextVisible(False)
        progress.setFixedSize(200, 20)

        overlay_layout.addWidget(progress)
        self.loading_overlay.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.loading_overlay and self.central_tabs:
            rect = self.central_tabs.contentsRect().adjusted(10, 10, -10, -10)
            self.loading_overlay.setGeometry(rect)

    @QtCore.Slot()
    def _try_load_planet_from_cache(self):
        if not self.project_manager.current_project_path:
            return

        cache_file = Path(self.project_manager.current_project_path) / "cache" / "planet_geometry.npz"
        if cache_file.exists():
            try:
                logger.info(f"Загрузка геометрии планеты из кэша: {cache_file}")
                data = np.load(cache_file, allow_pickle=True)
                self._on_planet_generation_finished({
                    "vertices": data["vertices"],
                    "fill_indices": data["fill_indices"],
                    "line_indices": data["line_indices"],
                    "colors": data["colors"],
                    "planet_data": data["planet_data"].item()
                })
            except Exception as e:
                logger.error(f"Ошибка загрузки кэша планеты: {e}")

    @QtCore.Slot()
    def _update_planet_view(self):
        self.loading_overlay.setParent(self.planet_widget.parent())
        self.loading_overlay.raise_()
        self.loading_overlay.show()

        worker = PlanetGenerationWorker(self)
        worker.signals.finished.connect(self._on_planet_generation_finished)
        worker.signals.error.connect(self._on_generation_error)
        self.thread_pool.start(worker)

    @QtCore.Slot(object)
    def _on_planet_generation_finished(self, result_data: dict):
        self.loading_overlay.hide()
        if self.planet_widget:
            self.planet_widget.set_planet_data(result_data["planet_data"])
            self.planet_widget.set_geometry(
                result_data["vertices"],
                result_data["fill_indices"],
                result_data["line_indices"],
                result_data["colors"]
            )
        logger.info("3D-вид планеты успешно обновлен (из потока).")

    @QtCore.Slot()
    def _on_apply_clicked(self):
        self.loading_overlay.setParent(self.preview_widget)
        self.loading_overlay.raise_()
        self.loading_overlay.show()
        if self.right_outliner:
            self.right_outliner.set_busy(True)

        worker = PreviewGenerationWorker(self)
        worker.signals.finished.connect(self._on_preview_generation_finished)
        worker.signals.error.connect(self._on_generation_error)
        self.thread_pool.start(worker)

    @QtCore.Slot(object)
    def _on_preview_generation_finished(self, result_data: Optional[Dict[str, Any]]):
        self.loading_overlay.hide()
        if self.right_outliner:
            self.right_outliner.set_busy(False)

        if result_data is None:
            logger.warning("Генерация превью не вернула данных (нода не выбрана?).")
            return

        # --- НОВАЯ ЛОГИКА: Обновление списка биомов ---
        if self.biome_probabilities_list:
            self.biome_probabilities_list.clear()
            probabilities = result_data.get("biome_probabilities", {})
            if probabilities:
                if "error" in probabilities:
                    self.biome_probabilities_list.addItem("Ошибка расчета климата")
                else:
                    sorted_probs = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)
                    for biome_name, prob in sorted_probs:
                        if prob < 0.001: continue # Не показывать слишком маловероятные
                        item_text = f"{biome_name.replace('_', ' ').title()}: {prob:.1%}"
                        self.biome_probabilities_list.addItem(item_text)
            else:
                self.biome_probabilities_list.addItem("Климат отключен")

        try:
            final_map_01 = result_data["final_map_01"]
            max_height = result_data["max_height"]
            vertex_distance = result_data["vertex_distance"]

            preview_res_str = self.preview_resolution_input.currentText()
            preview_resolution = int(preview_res_str.split('x')[0])

            display_map_01 = final_map_01
            scaling_factor = 1.0

            if final_map_01.shape[0] != preview_resolution:
                original_resolution = final_map_01.shape[0]
                logger.debug(f"Масштабирование карты с {original_resolution}px до {preview_resolution}px для превью.")

                if preview_resolution > 0:
                    scaling_factor = original_resolution / preview_resolution

                display_map_01 = cv2.resize(final_map_01, (preview_resolution, preview_resolution),
                                            interpolation=cv2.INTER_AREA)

            final_map_meters = (display_map_01 * max_height) / scaling_factor

            if self.preview_widget:
                self.preview_widget.update_mesh(final_map_meters, vertex_distance,
                                                north_vector_2d=result_data.get("north_vector_2d"))

            if self.node_inspector:
                self.node_inspector.refresh_from_selection()

            logger.info("3D-превью успешно обновлено.")

        except Exception as e:
            tb = traceback.format_exc()
            self._on_generation_error(f"Ошибка при обновлении UI: {e}\n\n{tb}")

    @QtCore.Slot(str)
    def _on_generation_error(self, error_message: str):
        self.loading_overlay.hide()
        if self.right_outliner:
            self.right_outliner.set_busy(False)
        logger.error(error_message)
        QtWidgets.QMessageBox.critical(self, "Ошибка в фоновом потоке", error_message)

    def _connect_components(self):
        # Подключение сигналов от виджетов к слотам
        if self.region_resolution_input:
            self.region_resolution_input.currentIndexChanged.connect(self._update_dynamic_ranges)
            self.region_resolution_input.currentIndexChanged.connect(self._update_calculated_fields)
        if self.vertex_distance_input: self.vertex_distance_input.valueChanged.connect(self._update_calculated_fields)
        if self.subdivision_level_input: self.subdivision_level_input.currentIndexChanged.connect(
            self._update_calculated_fields)
        if self.planet_type_preset_input: self.planet_type_preset_input.currentIndexChanged.connect(
            self._update_calculated_fields)
        if self.preview_resolution_input: self.preview_resolution_input.currentIndexChanged.connect(
            self._trigger_preview_update)

        if self.update_planet_btn:
            self.update_planet_btn.clicked.connect(self._update_planet_view)

        if self.planet_widget:
            self.planet_widget.cell_picked.connect(self._on_cell_picked)

        # --- ДОБАВЛЕНЫ НОВЫЕ ВИДЖЕТЫ КЛИМАТА В СПИСОК ---
        controls_for_dirty_mark = [
            self.subdivision_level_input, self.planet_preview_detail_input, self.region_resolution_input,
            self.vertex_distance_input, self.planet_type_preset_input, self.ws_relative_scale,
            self.ws_octaves, self.ws_gain, self.ws_power, self.ws_warp_strength, self.ws_seed,
            self.climate_enabled, self.climate_sea_level, self.climate_avg_temp,
            self.climate_axis_tilt, self.climate_wind_strength
        ]
        for control in controls_for_dirty_mark:
            if not control: continue
            if hasattr(control, 'editingFinished'):
                control.editingFinished.connect(self._mark_dirty)
            elif hasattr(control, 'valueChanged'):
                control.valueChanged.connect(self._mark_dirty)
            elif hasattr(control, 'toggled'):
                control.toggled.connect(self._mark_dirty)
            elif hasattr(control, 'currentIndexChanged'):
                control.currentIndexChanged.connect(self._mark_dirty)

        if self.graph:
            if self.props_bin: self.props_bin.set_graph(self.graph, self)
            if self.node_inspector: self.node_inspector.bind_graph(self.graph)
            if self.right_outliner: self.right_outliner.bind_graph(self.graph)
            if self.left_palette: self.left_palette.bind_graph(self.graph)
            QtCore.QTimer.singleShot(0, self.graph.finalize_setup)
            self.graph.selection_changed.connect(self._on_node_selection_changed)
            self.graph.structure_changed.connect(self._mark_dirty)

        if self.right_outliner:
            self.right_outliner.apply_clicked.connect(self._on_apply_clicked)
            self.right_outliner.export_clicked.connect(self._on_export_clicked)

        if self.presets_widget:
            self.presets_widget.load_requested.connect(self.action_load_region_preset)
            self.presets_widget.create_from_current_requested.connect(self.action_create_preset_from_dialog)
            self.presets_widget.delete_requested.connect(self.action_delete_preset_by_name)
            self.presets_widget.save_as_requested.connect(self.action_save_active_preset)

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

    @QtCore.Slot(int)
    def _on_cell_picked(self, cell_id: int):
        logger.info(f"Выбран регион (гекс) с ID: {cell_id}")
        self.current_region_id = cell_id

        planet_data = getattr(self.planet_widget, '_planet_data', None)
        if planet_data and 'centers_xyz' in planet_data and cell_id < len(planet_data['centers_xyz']):
            center_xyz = planet_data['centers_xyz'][cell_id]
            self.current_world_offset = tuple(center_xyz.tolist())

            if self.region_id_label: self.region_id_label.setText(str(cell_id))
            if self.region_center_x_label: self.region_center_x_label.setText(f"{self.current_world_offset[0]:.3f}")
            if self.region_center_z_label: self.region_center_z_label.setText(f"{self.current_world_offset[2]:.3f}")

        self._trigger_preview_update()

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

    def _update_calculated_fields(self):
        if not all([self.subdivision_level_input, self.region_resolution_input, self.vertex_distance_input,
                    self.planet_radius_label, self.base_elevation_label, self.max_height_input,
                    self.planet_type_preset_input]):
            return

        try:
            res_str = self.region_resolution_input.currentText()
            resolution = int(res_str.split('x')[0])
            dist = self.vertex_distance_input.value()
            region_side_m = resolution * dist
            hex_area_m2 = (region_side_m ** 2) * (math.sqrt(3) / 2)
            subdiv_text = self.subdivision_level_input.currentText()
            num_regions_str = "".join(filter(str.isdigit, subdiv_text))
            num_regions = int(num_regions_str) if num_regions_str else 0
            total_surface_area_m2 = num_regions * hex_area_m2
            radius_m = math.sqrt(total_surface_area_m2 / (4 * math.pi))
            radius_km = radius_m / 1000.0
            self.planet_radius_label.setText(f"{radius_km:,.0f} км")

            preset_name = self.planet_type_preset_input.currentText()
            roughness_pct, max_h_multiplier = PLANET_ROUGHNESS_PRESETS.get(preset_name, (0.003, 2.5))

            base_elevation = radius_m * roughness_pct
            max_h = base_elevation * max_h_multiplier

            self.base_elevation_label.setText(f"{base_elevation:,.0f} м")
            self.max_height_input.blockSignals(True)
            self.max_height_input.setValue(max_h)
            self.max_height_input.blockSignals(False)

            logger.debug(
                f"Расчет высот: Тип='{preset_name}', Шероховатость={roughness_pct * 100:.3f}%, "
                f"Радиус={radius_km:.1f}км -> Базовый перепад={base_elevation:.1f}м, "
                f"Макс. высота={max_h:.1f}м"
            )

        except Exception as e:
            logger.error(f"Ошибка при расчете полей: {e}")
            self.planet_radius_label.setText("Ошибка")
            self.base_elevation_label.setText("Ошибка")
            self.max_height_input.setValue(0)

    @QtCore.Slot(object)
    def _on_render_settings_changed(self, new_settings: RenderSettings):
        self.render_settings = new_settings
        if self.preview_widget:
            self.preview_widget.apply_render_settings(new_settings)
        if self.planet_widget and hasattr(self.planet_widget, 'set_render_settings'):
            self.planet_widget.set_render_settings(new_settings)

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

    def save_project(self):
        on_save_project(self)

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

    @QtCore.Slot()
    def _on_export_clicked(self):
        """Слот для обработки нажатия кнопки экспорта."""
        export_actions.run_region_export(self)

    def _mark_dirty(self, *_args, **_kwargs):
        self.project_manager.mark_dirty(True)

    def closeEvent(self, ev: QtGui.QCloseEvent):
        self._save_app_settings()
        if self.project_manager.close_project_with_confirmation():
            ev.accept()
        else:
            ev.ignore()

    def _trigger_apply(self) -> None:
        if self.right_outliner and self.right_outliner.apply_button:
            self.right_outliner.apply_button.animateClick(10)

    def show_planet_view(self):
        if self.central_tabs:
            for i in range(self.central_tabs.count()):
                if self.central_tabs.tabText(i) == "Планета":
                    self.central_tabs.setCurrentIndex(i)
                    if self.planet_widget and self.planet_widget._vbo_pos is None:
                        self._update_planet_view()
                    break

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