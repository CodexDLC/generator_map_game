# editor/widgets/preview_widget.py
from __future__ import annotations
import gc
import logging
import math
import numpy as np
from PySide6 import QtWidgets, QtCore
from vispy import scene, gloo

from editor.core.render_settings import RenderSettings
from editor.render_palettes import map_palette_cpu

logger = logging.getLogger(__name__)

def _normalize_01(z: np.ndarray) -> tuple[np.ndarray, float, float]:
    zmin = float(np.nanmin(z));
    zmax = float(np.nanmax(z))
    if zmax - zmin < 1e-12:
        return np.zeros_like(z, dtype=np.float32), zmin, zmax
    out = (z - zmin) / (zmax - zmin)
    return out.astype(np.float32, copy=False), zmin, zmax

def _dir_from_angles(az_deg: float, alt_deg: float) -> tuple[float, float, float]:
    az = math.radians(az_deg);
    alt = math.radians(alt_deg)
    x = math.cos(alt) * math.cos(az)
    y = math.cos(alt) * math.sin(az)
    z = math.sin(alt)
    return (-x, -y, -z)

class Preview3DWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._mesh = None
        self._globe = None            # MeshVisual для шара
        self._hex_lines = None        # LineVisual для гекс-контуров
        self._centers_xyz = None      # (N,3) float32 центры регионов (единичная сфера)
        self._lon0 = 0.0              # нулевой меридиан (рад)
        self._settings = RenderSettings()

        self.canvas = scene.SceneCanvas(keys="interactive", show=False, config={"samples": 4})
        self.view = self.canvas.central_widget.add_view()
        self.view.bgcolor = 'black'
        self.view.camera = scene.cameras.TurntableCamera(up='z', fov=self._settings.fov,
                                                         azimuth=45.0, elevation=30.0)
        scene.visuals.XYZAxis(parent=self.view.scene)
        lay = QtWidgets.QVBoxLayout(self);
        lay.setContentsMargins(0, 0, 0, 0);
        lay.addWidget(self.canvas.native)

    def _clear_scene(self) -> None:
        for v in (self._mesh, self._globe, self._hex_lines):
            if v is not None:
                v.parent = None
        self._mesh = None
        self._globe = None
        self._hex_lines = None
        gc.collect()

    def _icosphere(self, f_vis: int = 32):
        # берём твой сабдив из topology, чтобы не плодить код
        from generator_logic.topology.icosa_grid import _icosahedron as _ico
        V0, F0 = _ico()
        # простой равномерный сабдив «на полёт» (достаточно для предпросмотра):
        V = [v/np.linalg.norm(v) for v in V0]
        F = F0.copy()
        for _ in range(max(1, int(f_vis // 8))):  # грубая зависимость
            newF = []
            mid_cache = {}
            V = np.array(V, dtype=np.float32).tolist()
            def mid(a,b):
                key = (a,b) if a<b else (b,a)
                if key in mid_cache: return mid_cache[key]
                p = (np.array(V[a])+np.array(V[b]))*0.5
                p = (p/np.linalg.norm(p)).astype(np.float32)
                V.append(p.tolist())
                idx = len(V)-1
                mid_cache[key]=idx
                return idx
            for (a,b,c) in F:
                ab = mid(a,b); bc = mid(b,c); ca = mid(c,a)
                newF += [(a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca)]
            F = np.array(newF, dtype=np.int32)
        V = np.array(V, dtype=np.float32)
        return V, F

    def _sample_height_equirect(self, height_map: np.ndarray, p_xyz: np.ndarray, lon0: float):
        # p_xyz: (...,3) единичные
        x,y,z = p_xyz[...,0], p_xyz[...,1], p_xyz[...,2]
        lon = np.arctan2(y, x) - lon0           # [-pi..pi)
        lon = (lon + np.pi) % (2*np.pi) - np.pi
        lat = np.arcsin(np.clip(z, -1.0, 1.0))  # [-pi/2..pi/2]
        H, W = height_map.shape[:2]
        u = (lon/(2*np.pi) + 0.5) * (W-1)
        v = ((lat/np.pi) + 0.5) * (H-1)
        # билинейная интерполяция
        x0 = np.floor(u).astype(np.int32); x1 = np.clip(x0+1, 0, W-1)
        y0 = np.floor(v).astype(np.int32); y1 = np.clip(y0+1, 0, H-1)
        fu = (u - x0)[...,None]; fv = (v - y0)[...,None]
        q00 = height_map[y0, x0][...,None]
        q10 = height_map[y0, x1][...,None]
        q01 = height_map[y1, x0][...,None]
        q11 = height_map[y1, x1][...,None]
        h0 = q00*(1-fu) + q10*fu
        h1 = q01*(1-fu) + q11*fu
        h  = (h0*(1-fv) + h1*fv).squeeze(-1)
        return h.astype(np.float32)

    def _make_hex_lines(self, polys_lonlat_rad, lon0: float, radius: float = 1.001, color=(0,1,0,0.7), width=1.0):
        segs = []
        for poly in polys_lonlat_rad:
            if poly.shape[0] < 2: 
                continue
            # замкнутый контур
            for k in range(len(poly)):
                lon, lat = float(poly[k,0]), float(poly[k,1])
                lon = ((lon - lon0 + np.pi) % (2*np.pi)) - np.pi
                c = math.cos(lat)
                p1 = np.array([math.cos(lon)*c, math.sin(lon)*c, math.sin(lat)], dtype=np.float32) * radius
                lon2, lat2 = float(poly[(k+1)%len(poly),0]), float(poly[(k+1)%len(poly),1])
                lon2 = ((lon2 - lon0 + np.pi) % (2*np.pi)) - np.pi
                c2 = math.cos(lat2)
                p2 = np.array([math.cos(lon2)*c2, math.sin(lon2)*c2, math.sin(lat2)], dtype=np.float32) * radius
                segs.append([p1, p2])
        if not segs:
            return None
        pts = np.array(segs, dtype=np.float32).reshape(-1,3)
        connect = np.arange(len(pts)).reshape(-1,2)
        lines = scene.visuals.Line(pos=pts, connect=connect, color=color, width=width, method='gl')
        lines.parent = self.view.scene
        return lines

    def apply_render_settings(self, s: RenderSettings) -> None:
        self._settings = s
        cam = self.view.camera
        if hasattr(cam, "fov"): cam.fov = float(s.fov)

        if self.parent() and hasattr(self.parent(), '_on_apply_clicked'):
            QtCore.QTimer.singleShot(0, self.parent()._on_apply_clicked)

    def update_mesh(self, height_map: np.ndarray, cell_size: float, **kwargs) -> None:
        self._clear_scene()
        if not isinstance(height_map, np.ndarray) or height_map.shape[0] < 2 or height_map.shape[1] < 2:
            return

        if not np.all(np.isfinite(height_map)):
            return

        s = self._settings
        
        z = (height_map * float(s.height_exaggeration)).astype(np.float32, copy=False)
        
        self._mesh = scene.visuals.SurfacePlot(z=z, parent=self.view.scene)
        self._mesh.unfreeze()

        if s.use_palette:
            self._mesh.shading = None
            z01, _, _ = _normalize_01(z)
            gy, gx = np.gradient(z, cell_size)
            normals = np.stack([-gx, -gy, np.ones_like(z)], axis=-1)
            norm = np.linalg.norm(normals, axis=2, keepdims=True)
            normals /= np.maximum(norm, 1e-6)
            light_dir = np.array(_dir_from_angles(s.light_azimuth_deg, s.light_altitude_deg), dtype=np.float32)
            diffuse_intensity = np.maximum(0, np.dot(normals, -light_dir))
            light_intensity = s.ambient + s.diffuse * diffuse_intensity
            rgb_height = map_palette_cpu(z01, s.palette_name)
            slope_mult = np.ones_like(z, dtype=np.float32)
            if s.use_slope_darkening:
                slope = np.sqrt(gx * gx + gy * gy)
                slope_clipped = np.clip(slope * 0.5, 0.0, 1.0)
                slope_mult = 1.0 - s.slope_strength * slope_clipped
            final_rgb = rgb_height * light_intensity[..., None] * slope_mult[..., None]
            final_rgb = np.clip(final_rgb, 0.0, 1.0)
            alpha = np.ones((*final_rgb.shape[:2], 1), dtype=np.float32)
            rgba_3d = np.concatenate([final_rgb, alpha], axis=-1)
            self._mesh.mesh_data.set_vertex_colors(rgba_3d.reshape(-1, 4))
            self._mesh._need_color_update = True
        else:
            self._mesh.shading = 'smooth'
            base = float(max(0.05, min(2.0, s.diffuse)))
            self._mesh.color = (0.8 * base, 0.8 * base, 0.8 * base, 1.0)
            if hasattr(self._mesh, 'light'):
                L = _dir_from_angles(s.light_azimuth_deg, s.light_altitude_deg)
                self._mesh.light.direction = L
                self._mesh.light.ambient = float(s.ambient)
                self._mesh.light.specular = (s.specular, s.specular, s.specular, 1.0)
                self._mesh.light.shininess = float(s.shininess)

        self._mesh.freeze()
        self._mesh.transform = scene.transforms.MatrixTransform()
        self._mesh.transform.scale((cell_size, cell_size, 1.0))

        if s.auto_frame:
            h, w = height_map.shape
            zmin, zmax = float(np.nanmin(z)), float(np.nanmax(z))
            self.view.camera.set_range(x=(0, w * cell_size), y=(0, h * cell_size), z=(zmin, zmax))
            self.view.camera.distance = 1.8 * max(w * cell_size, h * cell_size)

        self.canvas.update()

    def update_globe(self, height_map: np.ndarray, disp: float,
                 centers_xyz: np.ndarray,
                 cell_polys_lonlat_rad: list[np.ndarray],
                 lon0_rad: float) -> None:
        """Рендерит шар с рельефом из height_map и линиями гексов."""
        self._clear_scene()
        self._centers_xyz = centers_xyz.astype(np.float32)
        self._lon0 = float(lon0_rad)

        V, F = self._icosphere(f_vis=32)  # визуальная частота (можешь поднять)
        # нормируем карту в [0..1]
        hm = np.asarray(height_map, dtype=np.float32)
        hmn, zmin, zmax = _normalize_01(hm)
        # сэмплим высоту и делаем дислпейс вдоль нормали
        h = self._sample_height_equirect(hmn, V, self._lon0)   # [0..1]
        R = 1.0 + disp * (h - 0.5)                             # радиус на вершине
        Vd = (V / np.linalg.norm(V, axis=1, keepdims=True)) * R[:,None]

        # меш шара
        self._globe = scene.visuals.Mesh(vertices=Vd, faces=F, shading='smooth', parent=self.view.scene)
        base = float(max(0.05, min(2.0, self._settings.diffuse)))
        self._globe.color = (0.75*base, 0.75*base, 0.78*base, 1.0)

        # линии гексов
        self._hex_lines = self._make_hex_lines(cell_polys_lonlat_rad, self._lon0, radius=1.001, color=(0,1,0,0.85), width=1.0)

        # автофрейм
        if self._settings.auto_frame:
            self.view.camera.set_range(x=(-1.2,1.2), y=(-1.2,1.2), z=(-1.2,1.2))
            self.view.camera.distance = 3.0

        # клик → ближайший центр (экранный pixel → ближайший в 2D-проекции центров)
        self.canvas.events.mouse_press.disconnect() if self.canvas.events.mouse_press.callbacks else None
        @self.canvas.events.mouse_press.connect
        def _on_click(ev):
            if self._centers_xyz is None: 
                return
            # проектируем центры в экранные координаты и ищем ближайший
            tr = self.view.scene.node_transform(self.canvas)
            pts2d = tr.map(self._centers_xyz)  # (N,4) hom
            xs = pts2d[:,0] / np.maximum(1e-6, pts2d[:,3])
            ys = pts2d[:,1] / np.maximum(1e-6, pts2d[:,3])
            mx, my = ev.pos
            d2 = (xs - mx)**2 + (ys - my)**2
            idx = int(np.argmin(d2))
            # тут же можно подсветить выбранный полигон/центр
            logger.info(f"[Globe] Picked cell #{idx}")
            # если нужно в метры — позови твой перевод из xyz→метры
        self.canvas.update()

    def closeEvent(self, e):
        self._clear_scene()
        self.canvas.close()
        super().closeEvent(e)
