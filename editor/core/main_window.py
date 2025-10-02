# editor/core/main_window.py
from __future__ import annotations
import logging
import traceback
from typing import Optional, Dict, Any

import numpy as np
from PySide6 import QtWidgets, QtCore, QtGui
from editor.graph.graph_runner import run_graph
from editor.ui_panels.accordion_properties import create_properties_widget, SliderSpinCombo, SeedWidget, CollapsibleBox
from editor.ui_panels.central_graph import create_bottom_work_area_v2
from editor.ui_panels.menu import build_menus
from editor.ui_panels.node_inspector import make_node_inspector_widget
from editor.ui_panels.region_presets_panel import make_region_presets_widget
from editor.ui_panels.shortcuts import install_shortcuts
from editor.widgets.preview_widget import Preview3DWidget
from editor.core.project_manager import ProjectManager
from editor.actions import preset_actions
from editor.ui_panels.world_settings_panel import make_world_settings_widget
from editor.ui_panels.render_panel import make_render_panel_widget
from editor.core.render_settings import RenderSettings

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

        self.graph: 'CustomNodeGraph' | None = None
        self.preview_widget: Preview3DWidget | None = None
        self.props_bin: QtWidgets.QWidget | None = None
        self.right_outliner: 'RightOutlinerWidget' | None = None
        self.left_palette: QtWidgets.QWidget | None = None
        self.node_inspector: QtWidgets.QWidget | None = None
        self.presets_widget: 'RegionPresetsWidget' | None = None
        self._last_selected_node = None

        self.global_x_offset_input: QtWidgets.QDoubleSpinBox | None = None
        self.global_z_offset_input: QtWidgets.QDoubleSpinBox | None = None
        self.world_size_input: QtWidgets.QDoubleSpinBox | None = None
        self.max_height_input: QtWidgets.QDoubleSpinBox | None = None
        self.vertex_spacing_input: QtWidgets.QDoubleSpinBox | None = None
        self.resolution_input: QtWidgets.QComboBox | None = None
        self.realtime_checkbox: QtWidgets.QCheckBox | None = None
        self.ws_noise_box: CollapsibleBox | None = None
        self.ws_fractal_type: QtWidgets.QComboBox | None = None
        self.ws_fractal_scale: SliderSpinCombo | None = None
        self.ws_fractal_octaves: SliderSpinCombo | None = None
        self.ws_fractal_roughness: SliderSpinCombo | None = None
        self.ws_fractal_seed: SeedWidget | None = None
        self.ws_var_strength: SliderSpinCombo | None = None
        self.ws_var_smoothness: SliderSpinCombo | None = None
        self.ws_var_contrast: SliderSpinCombo | None = None
        self.ws_var_damping: SliderSpinCombo | None = None
        self.ws_var_bias: SliderSpinCombo | None = None
        self.ws_warp_type: QtWidgets.QComboBox | None = None
        self.ws_warp_rel_size: SliderSpinCombo | None = None
        self.ws_warp_strength: SliderSpinCombo | None = None

        self._build_ui()
        build_menus(self)
        install_shortcuts(self)
        if project_path:
            self.project_manager.load_project(project_path)

    def _build_ui(self) -> None:
        try:
            self.preview_widget = Preview3DWidget(self)
            self.preview_widget.setParent(self)
        except (ImportError, RuntimeError) as e:
            logger.exception(f"Не удалось создать Preview3DWidget: {e}")
            self.preview_widget = QtWidgets.QLabel("Preview widget failed to load")
            self.preview_widget.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        bottom_work_area, self.graph, self.left_palette, self.right_outliner = create_bottom_work_area_v2(self)
        tabs_left = self._create_left_tabs()
        tabs_right = self._create_right_tabs()

        top_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal, self)
        top_splitter.addWidget(tabs_left)
        top_splitter.addWidget(self.preview_widget)
        top_splitter.addWidget(tabs_right)
        top_splitter.setStretchFactor(1, 1)
        top_splitter.setSizes([360, 900, 420])

        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical, self)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(bottom_work_area)
        main_splitter.setSizes([int(self.height() * 0.55), int(self.height() * 0.45)])
        self.setCentralWidget(main_splitter)
        self._connect_components()

    def _create_right_tabs(self) -> QtWidgets.QTabWidget:
        tabs = QtWidgets.QTabWidget()
        tabs.setObjectName("TopTabsRight")
        tabs.setDocumentMode(True)
        self.props_bin = create_properties_widget(self)
        tabs.addTab(self.props_bin, "Параметры")
        self.node_inspector = make_node_inspector_widget(self)
        tabs.addTab(self.node_inspector, "Инспектор")
        self.render_panel = make_render_panel_widget(
            self, self.render_settings, self._on_render_settings_changed
        )
        tabs.addTab(self.render_panel, "Рендер")
        return tabs

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

    def _connect_components(self):
        if self.global_x_offset_input: self.global_x_offset_input.editingFinished.connect(self._trigger_preview_update)
        if self.global_z_offset_input: self.global_z_offset_input.editingFinished.connect(self._trigger_preview_update)
        if self.world_size_input: self.world_size_input.editingFinished.connect(self._trigger_preview_update)
        if self.max_height_input: self.max_height_input.editingFinished.connect(self._trigger_preview_update)
        if self.resolution_input: self.resolution_input.currentIndexChanged.connect(self._trigger_preview_update)
        if self.ws_noise_box: self.ws_noise_box.toggled.connect(self._trigger_preview_update)
        if self.ws_fractal_type: self.ws_fractal_type.currentIndexChanged.connect(self._trigger_preview_update)
        if self.ws_fractal_scale: self.ws_fractal_scale.editingFinished.connect(self._trigger_preview_update)
        if self.ws_fractal_octaves: self.ws_fractal_octaves.editingFinished.connect(self._trigger_preview_update)
        if self.ws_fractal_roughness: self.ws_fractal_roughness.editingFinished.connect(self._trigger_preview_update)
        if self.ws_fractal_seed: self.ws_fractal_seed.editingFinished.connect(self._trigger_preview_update)
        if self.ws_var_strength: self.ws_var_strength.editingFinished.connect(self._trigger_preview_update)
        if self.ws_var_smoothness: self.ws_var_smoothness.editingFinished.connect(self._trigger_preview_update)
        if self.ws_var_contrast: self.ws_var_contrast.editingFinished.connect(self._trigger_preview_update)
        if self.ws_var_damping: self.ws_var_damping.editingFinished.connect(self._trigger_preview_update)
        if self.ws_var_bias: self.ws_var_bias.editingFinished.connect(self._trigger_preview_update)
        if self.ws_warp_type: self.ws_warp_type.currentIndexChanged.connect(self._trigger_preview_update)
        if self.ws_warp_rel_size: self.ws_warp_rel_size.editingFinished.connect(self._trigger_preview_update)
        if self.ws_warp_strength: self.ws_warp_strength.editingFinished.connect(self._trigger_preview_update)
        if self.graph:
            if self.props_bin: self.props_bin.set_graph(self.graph, self)
            if self.node_inspector: self.node_inspector.bind_graph(self.graph)
            if self.right_outliner: self.right_outliner.bind_graph(self.graph)
            if self.left_palette: self.left_palette.bind_graph(self.graph)
            QtCore.QTimer.singleShot(0, self.graph.finalize_setup)
            self.graph.selection_changed.connect(self._on_node_selection_changed)
        if self.right_outliner:
            self.right_outliner.apply_clicked.connect(self._on_apply_clicked)
        if self.presets_widget:
            self.presets_widget.load_requested.connect(self.action_load_region_preset)
            self.presets_widget.create_from_current_requested.connect(self.action_create_preset_from_dialog)
            self.presets_widget.delete_requested.connect(self.action_delete_preset_by_name)
            self.presets_widget.save_as_requested.connect(self.action_save_active_preset)

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
        if self.realtime_checkbox.isChecked():
            self._on_apply_clicked()

    @QtCore.Slot(list)
    def _on_node_selection_changed(self, selected_nodes):
        if selected_nodes:
            self._last_selected_node = selected_nodes[0]
            if self.realtime_checkbox.isChecked():
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
            self.presets_widget.select_preset(preset_name)
            self._mark_dirty()

    def action_create_preset_from_dialog(self, _preset_name_from_field: str):
        preset_actions.handle_new_preset(self)

    def action_delete_preset_by_name(self, preset_name: str):
        items = self.presets_widget.list.findItems(preset_name, QtCore.Qt.MatchFlag.MatchExactly)
        if items:
            self.presets_widget.list.setCurrentItem(items[0])
            preset_actions.handle_delete_preset(self)

    def action_save_active_preset(self):
        preset_actions.handle_save_active_preset(self)

    def _mark_dirty(self, *_args, **_kwargs):
        self.project_manager.mark_dirty(True)

    def closeEvent(self, ev: QtGui.QCloseEvent):
        if self.project_manager.close_project_with_confirmation():
            ev.accept()
        else:
            ev.ignore()

    def _on_apply_clicked(self):
        if self.right_outliner: self.right_outliner.set_busy(True)
        try:
            target_node = self.graph.selected_nodes()[0] if self.graph.selected_nodes() else self._last_selected_node
            if not target_node:
                logger.warning("Нет выбранной ноды для превью. Рендер отменен.")
                return

            logger.info(f"Рендеринг превью для ноды: '{target_node.name()}'")
            context = self.project_manager.collect_ui_context()
            from generator_logic.terrain.fractals import multifractal_wrapper

            world_size = context.get('WORLD_SIZE_METERS', 5000.0)
            max_height = self.max_height_input.value()

            if self.ws_noise_box.isChecked():
                fractal_params = {
                    'type': self.ws_fractal_type.currentText().lower(),
                    'scale': self.ws_fractal_scale.value() / 100.0,
                    'octaves': int(self.ws_fractal_octaves.value()),
                    'roughness': self.ws_fractal_roughness.value(),
                    'seed': self.ws_fractal_seed.value(),
                }
                variation_params = {'variation': self.ws_var_strength.value(),
                                    'smoothness': self.ws_var_smoothness.value(),
                                    'contrast': self.ws_var_contrast.value(), 'damping': self.ws_var_damping.value(),
                                    'bias': self.ws_var_bias.value(), }

                wt = self.ws_warp_type.currentText().lower()
                warp_freq = 1.0 / (world_size * max(self.ws_warp_rel_size.value(), 1e-6))
                warp_amp0_m = self.ws_warp_strength.value() * max_height

                warp_params_final = {'type': wt, 'frequency': warp_freq, 'amp0_m': warp_amp0_m, 'complexity': 3,
                                     'roughness': 0.5, 'attenuation': 1.0, 'iterations': 1, 'anisotropy': 1.0,
                                     'seed': fractal_params['seed']}

                # --- НОВАЯ ЛОГИКА: Подробный вывод в лог ---
                logger.debug(
                    f"Параметры Глобального Шума: fractal={fractal_params}, variation={variation_params}, warp={warp_params_final}")

                world_fractal_noise = multifractal_wrapper(context, fractal_params, variation_params, {},
                                                           warp_params_final)
            else:
                logger.debug("Глобальный шум выключен. Используется плоская карта.")
                world_fractal_noise = np.zeros_like(context["x_coords"], dtype=np.float32)

            context["world_input_noise"] = world_fractal_noise
            final_map_01 = run_graph(target_node, context)
            max_height_m = self.max_height_input.value()
            final_map_meters = final_map_01 * max_height_m

            if self.preview_widget:
                resolution_str = self.resolution_input.currentText()
                preview_res = int(resolution_str.split('x')[0])
                preview_vertex_spacing = world_size / preview_res
                self.preview_widget.update_mesh(final_map_meters, preview_vertex_spacing)

        except Exception as e:
            logger.exception(f"Ошибка во время генерации: {e}")
            QtWidgets.QMessageBox.critical(self, "Ошибка генерации",
                                           f"Произошла ошибка: {e}\n\n{traceback.format_exc()}")
        finally:
            if self.right_outliner: self.right_outliner.set_busy(False)

    def _trigger_apply(self) -> None:
        if self.right_outliner and self.right_outliner.apply_button:
            self.right_outliner.apply_button.animateClick(10)