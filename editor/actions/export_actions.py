# editor/actions/export_actions.py
import logging
import math
from pathlib import Path
import numpy as np
from PySide6 import QtWidgets, QtCore

# <<< ИЗМЕНЕНИЕ: Импортируем новую функцию >>>
from editor.logic.preview_logic import generate_node_graph_output
from game_engine_restructured.core.export import (
    write_world_meta_json,
    write_client_chunk_meta,
    write_heightmap_r16,
    write_control_map_r32
)
from game_engine_restructured.world.serialization import ClientChunkContract

logger = logging.getLogger(__name__)

VALID_CHUNK_SIZES = ["256", "512", "1024"]


class ExportDialog(QtWidgets.QDialog):
    """Диалоговое окно для настройки параметров экспорта."""

    def __init__(self, parent, last_dir: str | None):
        super().__init__(parent)
        self.setWindowTitle("Экспорт региона для движка")
        self.setMinimumWidth(400)

        self.layout = QtWidgets.QVBoxLayout(self)
        self.form_layout = QtWidgets.QFormLayout()

        self.path_edit = QtWidgets.QLineEdit(last_dir or "")
        self.path_button = QtWidgets.QPushButton("...")
        self.path_button.clicked.connect(self._select_path)
        path_layout = QtWidgets.QHBoxLayout()
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(self.path_button)
        self.form_layout.addRow("Папка для экспорта:", path_layout)

        self.chunk_size_combo = QtWidgets.QComboBox()
        self.chunk_size_combo.addItems(VALID_CHUNK_SIZES)
        self.chunk_size_combo.setCurrentText("512")
        self.form_layout.addRow("Размер чанка (px):", self.chunk_size_combo)

        self.world_id_edit = QtWidgets.QLineEdit("world_location")
        self.form_layout.addRow("ID мира:", self.world_id_edit)

        self.layout.addLayout(self.form_layout)

        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def _select_path(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Выберите папку для экспорта", self.path_edit.text()
        )
        if directory:
            self.path_edit.setText(directory)

    def get_settings(self) -> dict | None:
        if self.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            return {
                "output_path": self.path_edit.text(),
                "chunk_size": int(self.chunk_size_combo.currentText()),
                "world_id": self.world_id_edit.text().strip() or "world_location"
            }
        return None


def run_region_export(main_window):
    """Главная функция-оркестратор экспорта."""
    settings = QtCore.QSettings("WorldForge", "Editor")
    last_dir = settings.value("last_export_dir", "")

    dialog = ExportDialog(main_window, last_dir)
    export_settings = dialog.get_settings()
    if not export_settings:
        logger.info("Экспорт отменен пользователем.")
        return

    settings.setValue("last_export_dir", export_settings["output_path"])

    chunk_size = export_settings["chunk_size"]
    world_id = export_settings["world_id"]
    base_path = Path(export_settings["output_path"])

    world_seed_for_path = "25" # TODO: Get from project settings
    world_path = base_path / world_id / world_seed_for_path

    logger.info(f"Начало экспорта региона в '{world_path}' с размером чанка {chunk_size}x{chunk_size}")

    main_window.loading_overlay.show()
    QtWidgets.QApplication.processEvents()

    try:
        # <<< ИЗМЕНЕНИЕ: Вызываем новую функцию с флагом for_export=True >>>
        export_data = generate_node_graph_output(main_window, for_export=True)
        if not export_data:
            raise RuntimeError("Не удалось сгенерировать данные для экспорта (нода не выбрана?).")

        heightmap_full = export_data["final_map_01"] * export_data["max_height"]
        region_res = heightmap_full.shape[0]

        if region_res % chunk_size != 0:
            raise ValueError(f"Разрешение региона ({region_res}) должно быть кратно размеру чанка ({chunk_size}).")

        world_meta_path = world_path / "_world_meta.json"
        world_path.mkdir(parents=True, exist_ok=True)

        write_world_meta_json(
            str(world_meta_path),
            world_id=world_id,
            hex_edge_m=0.63,
            chunk_px=chunk_size,
            meters_per_pixel=main_window.vertex_distance_input.value(),
            height_min_m=0.0,
            height_max_m=export_data["max_height"]
        )
        logger.info(f"Файл _world_meta.json сохранен.")

        num_chunks = region_res // chunk_size
        total_chunks = num_chunks * num_chunks
        logger.info(f"Регион будет разбит на {num_chunks}x{num_chunks} ({total_chunks}) чанков.")

        for cz in range(num_chunks):
            for cx in range(num_chunks):
                chunk_dir = world_path / f"{cx}_{cz}"
                chunk_dir.mkdir(parents=True, exist_ok=True)

                y_start, x_start = cz * chunk_size, cx * chunk_size
                height_chunk = heightmap_full[y_start:y_start + chunk_size, x_start:x_start + chunk_size]

                empty_surface = np.zeros((chunk_size, chunk_size), dtype=np.uint8)
                empty_nav = np.zeros((chunk_size, chunk_size), dtype=np.uint8)
                empty_overlay = np.zeros((chunk_size, chunk_size), dtype=np.uint8)

                write_heightmap_r16(str(chunk_dir / "heightmap.r16"), height_chunk.tolist(),
                                    h_norm=export_data["max_height"])
                write_control_map_r32(str(chunk_dir / "control.r32"), empty_surface, empty_nav, empty_overlay)

                chunk_contract = ClientChunkContract(cx=cx, cz=cz)
                write_client_chunk_meta(str(chunk_dir / "chunk.json"), chunk_contract)

        logger.info("Экспорт успешно завершен!")
        QtWidgets.QMessageBox.information(main_window, "Успех", f"Регион успешно экспортирован в:\n{world_path}")

    except Exception as e:
        logger.exception("Ошибка во время экспорта региона.")
        QtWidgets.QMessageBox.critical(main_window, "Ошибка экспорта", str(e))
    finally:
        main_window.loading_overlay.hide()