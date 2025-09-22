# ==============================================================================
# Файл: editor/preview_widget.py
# ВЕРСИЯ 2.2: Полный рабочий виджет 3D-превью с тайловым обновлением.
# ==============================================================================

import numpy as np
from PySide6 import QtCore, QtWidgets
from vispy import scene
import time, sys
def _vtrace(msg):
    print(f"[TRACE/VIEW] {msg}", flush=True, file=sys.stdout)


class Preview3DWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._upd_count = 0
        self._tile_count = 0

        # VisPy canvas
        self.canvas = scene.SceneCanvas(keys="interactive", show=False)
        self.view = self.canvas.central_widget.add_view()
        self.view.camera = "turntable"
        self.view.camera.fov = 45

        # Оси для ориентира
        scene.visuals.XYZAxis(parent=self.view.scene)

        # Контейнер в Qt
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas.native)

        # Данные
        self.surface = None
        self._full = None
        self._pending_redraw = False
        self._size = None          # (w, h) текущей геометрии SurfacePlot
        self._cell_size = 1.0      # последний cell_size (для прокси)
        self._proxy_step = 1       # шаг даунсемплинга для тайлов

    # ---------- ВСПОМОГАТЕЛЬНОЕ ----------

    def _ensure_surface(self, width_px: int, height_px: int, cell_size: float):
        t0 = time.perf_counter()
        import numpy as np
        w, h = int(width_px), int(height_px)
        need_recreate = (self.surface is None) or (self._size != (w, h))

        x = np.linspace(0, (w - 1) * cell_size, w, dtype=np.float32)
        z = np.linspace(0, (h - 1) * cell_size, h, dtype=np.float32)
        X, Z = np.meshgrid(x, z)

        if need_recreate:
            if self.surface is not None:
                try:
                    self.surface.parent = None
                except Exception:
                    pass
                self.surface = None
            self.surface = scene.visuals.SurfacePlot(
                x=X, y=Z, z=np.zeros((h, w), dtype=np.float32),
                shading="smooth", color=(0.72, 0.72, 0.76, 1.0),
                parent=self.view.scene
            )
            self._size = (w, h)
            _vtrace(f"surface RECREATE {w}x{h} cell={cell_size:.3f}")
        else:
            self.surface.set_data(x=X, y=Z)
            _vtrace(f"surface set XY {w}x{h} cell={cell_size:.3f}")

        self.view.camera.set_range(
            x=(0, x[-1] if x.size else 1),
            y=(0, z[-1] if z.size else 1),
            z=(0, max(w, h) * 0.5)
        )
        _vtrace(f"_ensure_surface done in {(time.perf_counter() - t0) * 1000:.1f} ms")

    def _request_redraw(self):
        """
        Просим перерисовку с троттлингом (раз в ~100 мс).
        """
        if not self._pending_redraw:
            self._pending_redraw = True
            QtCore.QTimer.singleShot(100, self._flush_redraw)
            _vtrace("schedule redraw (+100ms)")

    def _flush_redraw(self):
        t0 = time.perf_counter()
        self._pending_redraw = False
        if self.surface is None or self._full is None:
            return

        step = int(self._proxy_step)
        if step <= 1:
            self.surface.set_data(z=self._full)
            _vtrace(f"flush FULL set_data {(time.perf_counter() - t0) * 1000:.1f} ms")
            return

        proxy = self._full[::step, ::step]
        proxy_dim = proxy.shape[0]
        if self._size != (proxy_dim, proxy_dim):
            proxy_cell = self._cell_size * step
            self._ensure_surface(proxy_dim, proxy_dim, proxy_cell)
        t1 = time.perf_counter()
        self.surface.set_data(z=proxy)
        _vtrace(f"flush PROXY {proxy_dim}x{proxy_dim} step={step} "
                f"set_data={(time.perf_counter() - t1) * 1000:.1f} ms total={(time.perf_counter() - t0) * 1000:.1f} ms")

    # ---------- ПОЛНОЕ ОБНОВЛЕНИЕ ----------

    def update_mesh(self, height_map: np.ndarray, cell_size: float):
        t0 = time.perf_counter()
        if height_map is None:
            return
        h, w = int(height_map.shape[0]), int(height_map.shape[1])
        self._full = height_map.astype(np.float32, copy=True)
        self._cell_size = float(cell_size)
        self._proxy_step = 1  # полный рендер

        self._ensure_surface(w, h, self._cell_size)
        t1 = time.perf_counter()
        self.surface.set_data(z=self._full)
        t2 = time.perf_counter()
        self._upd_count += 1
        _vtrace(
            f"update_mesh z={w}x{h} set_data={(t2 - t1) * 1000:.1f} ms total={(t2 - t0) * 1000:.1f} ms (upd#{self._upd_count})")

    # ---------- ЧАСТИЧНОЕ ОБНОВЛЕНИЕ (ТАЙЛЫ) ----------

    def update_tile(self, tile_map: np.ndarray, tx: int, tz: int,
                    cs: int, rs: int, cell_size: float):
        t0 = time.perf_counter()
        if tile_map is None:
            return

        H = int(cs) * int(rs)
        self._cell_size = float(cell_size)

        if self._full is None or self._full.shape != (H, H):
            self._full = np.zeros((H, H), dtype=np.float32)
            self._proxy_step = max(1, int(np.ceil(H / PROXY_MAX_DIM)))
            proxy_cell = self._cell_size * self._proxy_step
            proxy_dim = (H // self._proxy_step)
            self._ensure_surface(proxy_dim, proxy_dim, proxy_cell)
            self.surface.set_data(z=self._full[::self._proxy_step, ::self._proxy_step])
            _vtrace(f"tile: init buffer H={H} step={self._proxy_step} proxy={proxy_dim}x{proxy_dim}")

        y0 = int(tz) * int(cs)
        x0 = int(tx) * int(cs)
        self._full[y0:y0 + cs, x0:x0 + cs] = tile_map.astype(np.float32, copy=False)
        self._tile_count += 1
        _vtrace(f"tile put ({tx},{tz}) at [{y0}:{y0 + cs},{x0}:{x0 + cs}] "
                f"cs={cs} rs={rs} step={self._proxy_step} tile#{self._tile_count} "
                f"put={(time.perf_counter() - t0) * 1000:.1f} ms")

        self._request_redraw()

