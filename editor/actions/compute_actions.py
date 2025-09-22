# ==============================================================================
# Файл: editor/actions/compute_actions.py
# ВЕРСИЯ 3.1: правильные конструкторы воркеров + подготовка контекста здесь.
# ==============================================================================

from __future__ import annotations

import numpy as np
from PySide6 import QtCore


# Импорты воркеров и диалога прогресса (как у тебя сейчас – из editor/actions)
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
    """
    Унифицированная привязка сигналов воркера к диалогу и потоку.
    """
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
    """
    Безопасно коннектим пользовательские слоты, если они есть.
    """
    if hasattr(worker, "partial_ready") and hasattr(main_window, "on_tile_ready"):
        worker.partial_ready.connect(main_window.on_tile_ready,
                                     type=QtCore.Qt.ConnectionType.QueuedConnection)
    if hasattr(worker, "finished") and hasattr(main_window, "on_compute_finished"):
        worker.finished.connect(main_window.on_compute_finished,
                                type=QtCore.Qt.ConnectionType.QueuedConnection)
    if hasattr(worker, "error") and hasattr(main_window, "on_compute_error"):
        worker.error.connect(main_window.on_compute_error,
                             type=QtCore.Qt.ConnectionType.QueuedConnection)


def _ui_params(main_window) -> dict:
    """
    Забираем параметры из инпутов и считаем размер H.
    """
    cs = int(main_window.chunk_size_input.value())
    rs = int(main_window.region_size_input.value())
    H  = cs * rs
    return {
        "chunk_size": cs,
        "region_size": rs,
        "H": H,
        "cell_size": float(main_window.cell_size_input.value()),
        "seed": int(main_window.seed_input.value()),
        "gx": float(main_window.global_x_offset_input.value()),
        "gz": float(main_window.global_z_offset_input.value()),
    }


# ------------------------------------------------------------------------------
# ПУБЛИЧНЫЕ ОБРАБОТЧИКИ
# ------------------------------------------------------------------------------

def on_apply_clicked(main_window):
    _trace("on_apply_clicked: start")

    ui = _ui_params(main_window)
    H = ui["H"]
    _trace(f"ui: H={H} cs={ui['chunk_size']} rs={ui['region_size']} "
           f"cell={ui['cell_size']} seed={ui['seed']} gx={ui['gx']} gz={ui['gz']}")

    xs = np.arange(H, dtype=np.float32) + ui["gx"]
    zs = np.arange(H, dtype=np.float32) + ui["gz"]
    X, Z = np.meshgrid(xs, zs)
    _trace(f"coords: X/Z ready shape={X.shape}")

    context = {
        "x_coords": X, "z_coords": Z,
        "cell_size": ui["cell_size"], "seed": ui["seed"],
        "global_x_offset": ui["gx"], "global_z_offset": ui["gz"],
        "chunk_size": ui["chunk_size"], "region_size_in_chunks": ui["region_size"],
    }
    _trace("context assembled")

    dlg = ProgressDialog(parent=main_window)
    dlg.setWindowTitle("Генерация (single)")
    dlg.set_busy(True)
    dlg.update_progress(0, "Подготовка...")
    dlg.open()
    _trace("ProgressDialog opened")

    thread = QtCore.QThread(parent=main_window)
    thread.setObjectName("ComputeThread")
    worker = ComputeWorker(graph=getattr(main_window, "graph", None),
                           context=context)
    worker.moveToThread(thread)
    _trace("worker created & moved to thread")

    _connect_worker_signals_for_dialog(worker, thread, dlg)
    _connect_worker_signals_for_mainwindow(main_window, worker)
    _trace("signals connected (dialog/mainwindow)")

    # Доп. трейсы
    thread.started.connect(lambda: _trace("thread.started"), type=QtCore.Qt.ConnectionType.QueuedConnection)
    thread.finished.connect(lambda: _trace("thread.finished"), type=QtCore.Qt.ConnectionType.QueuedConnection)
    worker.progress.connect(lambda p, m: _trace(f"worker.progress {p}% | {m}"), type=QtCore.Qt.ConnectionType.QueuedConnection)
    worker.finished.connect(lambda *_: _trace("worker.finished"), type=QtCore.Qt.ConnectionType.QueuedConnection)
    worker.error.connect(lambda m: _trace(f"worker.error: {m}"), type=QtCore.Qt.ConnectionType.QueuedConnection)

    # >>> ДЕРЖИМ ССЫЛКИ ДО КОНЦА РАБОТЫ <<<
    if not hasattr(main_window, "_jobs"):
        main_window._jobs = []
    main_window._jobs.append((thread, worker, dlg))

    def _cleanup():
        _trace("cleanup: removing job refs")
        try:
            main_window._jobs.remove((thread, worker, dlg))
        except ValueError:
            pass

    worker.finished.connect(_cleanup, type=QtCore.Qt.ConnectionType.QueuedConnection)
    worker.error.connect(_cleanup, type=QtCore.Qt.ConnectionType.QueuedConnection)

    thread.started.connect(worker.run)
    thread.start()
    _trace("thread.start() called")

def on_apply_tiled_clicked(main_window):
    """
    Тайловый прогон. Здесь НЕ создаём полные сетки X/Z, это делает сам воркер
    по каждому тайлу. Ему нужен базовый контекст и размеры тайла/региона.
    """
    _trace("on_apply_tiled_clicked: start")

    ui = _ui_params(main_window)
    _trace(f"ui: cs={ui['chunk_size']} rs={ui['region_size']} "
           f"cell={ui['cell_size']} seed={ui['seed']} gx={ui['gx']} gz={ui['gz']}")

    base_context = {
        "cell_size": ui["cell_size"],
        "seed": ui["seed"],
        "global_x_offset": ui["gx"],
        "global_z_offset": ui["gz"],
        "chunk_size": ui["chunk_size"],
        "region_size_in_chunks": ui["region_size"],
    }

    dlg = ProgressDialog(parent=main_window)
    dlg.setWindowTitle("Генерация (tiled)")
    dlg.set_busy(True)
    dlg.update_progress(0, "Разбиваем на тайлы...")
    dlg.open()
    _trace("ProgressDialog (tiled) opened")

    thread = QtCore.QThread(parent=main_window)
    thread.setObjectName("TiledComputeThread")
    worker = TiledComputeWorker(
        graph=getattr(main_window, "graph", None),
        base_context=base_context,
        chunk_size=ui["chunk_size"],
        region_size=ui["region_size"],
    )
    worker.moveToThread(thread)
    _trace("tiled worker created & moved to thread")

    _connect_worker_signals_for_dialog(worker, thread, dlg)
    _connect_worker_signals_for_mainwindow(main_window, worker)
    _trace("signals connected (dialog/mainwindow)")

    # Трейсы
    QC = QtCore.Qt.ConnectionType
    thread.started.connect(lambda: _trace("tiled thread.started"), type=QC.QueuedConnection)
    thread.finished.connect(lambda: _trace("tiled thread.finished"), type=QC.QueuedConnection)
    worker.progress.connect(lambda p, m: _trace(f"tiled progress {p}% | {m}"), type=QC.QueuedConnection)
    worker.finished.connect(lambda *_: _trace("tiled worker.finished"), type=QC.QueuedConnection)
    worker.error.connect(lambda m: _trace(f"tiled worker.error: {m}"), type=QC.QueuedConnection)
    worker.partial_ready.connect(lambda tx, tz, *_: _trace(f"tiled tile ready ({tx},{tz})"),
                                 type=QC.QueuedConnection)

    # >>> держим ссылки, как в single <<<
    if not hasattr(main_window, "_jobs"):
        main_window._jobs = []
    main_window._jobs.append((thread, worker, dlg))

    def _cleanup():
        _trace("tiled cleanup: removing job refs")
        try:
            main_window._jobs.remove((thread, worker, dlg))
        except ValueError:
            pass
    worker.finished.connect(_cleanup, type=QC.QueuedConnection)
    worker.error.connect(_cleanup, type=QC.QueuedConnection)

    thread.started.connect(worker.run)
    thread.start()
    _trace("tiled thread.start() called")
