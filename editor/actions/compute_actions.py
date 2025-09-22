# ==============================================================================
# Файл: editor/actions/compute_actions.py
# ВЕРСИЯ 3.2: Добавлен сбор данных из панели "Глобальный Шум".
# ==============================================================================

from __future__ import annotations

import numpy as np
from PySide6 import QtCore

from .worker import ComputeWorker, TiledComputeWorker
from .progress_dialog import ProgressDialog

import sys


def _trace(msg):
    print(f"[TRACE/APPLY] {msg}", flush=True, file=sys.stdout)


# ------------------------------------------------------------------------------
# Вспомогалки
# ------------------------------------------------------------------------------

def _connect_worker_signals_for_dialog(worker: QtCore.QObject,
                                       thread: QtCore.QThread,
                                       dlg: ProgressDialog) -> None:
    if hasattr(worker, "set_busy"):
        worker.set_busy.connect(dlg.set_busy, type=QtCore.Qt.ConnectionType.QueuedConnection)
    if hasattr(worker, "progress"):
        if hasattr(dlg, "log_progress"):
            worker.progress.connect(dlg.log_progress, type=QtCore.Qt.ConnectionType.QueuedConnection)
        else:
            worker.progress.connect(dlg.update_progress, type=QtCore.Qt.ConnectionType.QueuedConnection)

    if hasattr(worker, "finished"):
        worker.finished.connect(dlg.accept, type=QtCore.Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(thread.quit, type=QtCore.Qt.ConnectionType.QueuedConnection)
    if hasattr(worker, "error"):
        worker.error.connect(dlg.reject, type=QtCore.Qt.ConnectionType.QueuedConnection)
        worker.error.connect(thread.quit, type=QtCore.Qt.ConnectionType.QueuedConnection)

    thread.finished.connect(worker.deleteLater)
    if hasattr(dlg, "cancel_button") and hasattr(worker, "cancel"):
        dlg.cancel_button.clicked.connect(worker.cancel)


def _connect_worker_signals_for_mainwindow(main_window,
                                           worker: QtCore.QObject) -> None:
    if hasattr(worker, "partial_ready") and hasattr(main_window, "on_tile_ready"):
        worker.partial_ready.connect(main_window.on_tile_ready,
                                     type=QtCore.Qt.ConnectionType.QueuedConnection)
    if hasattr(worker, "finished") and hasattr(main_window, "on_compute_finished"):
        worker.finished.connect(main_window.on_compute_finished,
                                type=QtCore.Qt.ConnectionType.QueuedConnection)
    if hasattr(worker, "error") and hasattr(main_window, "on_compute_error"):
        worker.error.connect(main_window.on_compute_error,
                             type=QtCore.Qt.ConnectionType.QueuedConnection)


def _get_context_from_ui(main_window) -> dict:
    """Собирает все параметры из UI и формирует из них контекст для генерации."""
    # --- НОВЫЙ БЛОК: Собираем данные глобального шума ---
    global_noise_params = {
        "scale_tiles": main_window.gn_scale_input.value(),
        "octaves": main_window.gn_octaves_input.value(),
        "amp_m": main_window.gn_amp_input.value(),
        "ridge": main_window.gn_ridge_checkbox.isChecked()
    }

    cs = int(main_window.chunk_size_input.value())
    rs = int(main_window.region_size_input.value())
    H = cs * rs

    xs = np.arange(H, dtype=np.float32) + float(main_window.global_x_offset_input.value())
    zs = np.arange(H, dtype=np.float32) + float(main_window.global_z_offset_input.value())
    X, Z = np.meshgrid(xs, zs)

    return {
        "x_coords": X, "z_coords": Z,
        "cell_size": main_window.cell_size_input.value(),
        "seed": main_window.seed_input.value(),
        "global_x_offset": main_window.global_x_offset_input.value(),
        "global_z_offset": main_window.global_z_offset_input.value(),
        "chunk_size": cs,
        "region_size_in_chunks": rs,
        # --- ДОБАВЛЯЕМ ПАРАМЕТРЫ В КОНТЕКСТ ---
        "global_noise": global_noise_params
    }


# ------------------------------------------------------------------------------
# ПУБЛИЧНЫЕ ОБРАБОТЧИКИ
# ------------------------------------------------------------------------------

def on_apply_clicked(main_window):
    _trace("on_apply_clicked: start")
    context = _get_context_from_ui(main_window)
    _trace("context assembled")

    dlg = ProgressDialog(parent=main_window)
    dlg.setWindowTitle("Генерация (single)")
    dlg.open()

    thread = QtCore.QThread(parent=main_window)
    worker = ComputeWorker(graph=main_window.graph, context=context)
    worker.moveToThread(thread)

    _connect_worker_signals_for_dialog(worker, thread, dlg)
    _connect_worker_signals_for_mainwindow(main_window, worker)

    thread.started.connect(worker.run)
    thread.start()
    _trace("thread.start() called")


def on_apply_tiled_clicked(main_window):
    # Логика для тайлового рендера пока остается без изменений,
    # но в будущем ее тоже нужно будет адаптировать.
    _trace("on_apply_tiled_clicked: start")
    context = _get_context_from_ui(main_window)

    dlg = ProgressDialog(parent=main_window)
    dlg.setWindowTitle("Генерация (tiled)")
    dlg.open()

    thread = QtCore.QThread(parent=main_window)
    worker = TiledComputeWorker(
        graph=main_window.graph,
        base_context=context,  # Передаем полный контекст
        chunk_size=context["chunk_size"],
        region_size=context["region_size_in_chunks"],
    )
    worker.moveToThread(thread)

    _connect_worker_signals_for_dialog(worker, thread, dlg)
    _connect_worker_signals_for_mainwindow(main_window, worker)

    thread.started.connect(worker.run)
    thread.start()
    _trace("tiled thread.start() called")