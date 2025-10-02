from __future__ import annotations
from dataclasses import dataclass, asdict

@dataclass
class RenderSettings:
    # Свет/материал
    light_azimuth_deg: float = 45.0
    light_altitude_deg: float = 35.0
    ambient: float = 0.34
    diffuse: float = 1.00
    specular: float = 0.06
    shininess: float = 24.0
    light_mode: str = "world"   # "world" | "headlight"

    # Геометрия/камера
    height_exaggeration: float = 1.25
    fov: float = 45.0
    auto_frame: bool = True

    # Цвет
    use_palette: bool = True
    palette_name: str = "Rock"
    use_slope_darkening: bool = False
    slope_strength: float = 0.25

    @classmethod
    def from_dict(cls, d: dict) -> "RenderSettings":
        base = asdict(cls())
        base.update({k: d[k] for k in base.keys() if k in d})
        return cls(**base)

# Готовые пресеты (можно править на вкус)
RENDER_PRESETS: dict[str, dict] = {
    "Clay": {
        "light_azimuth_deg": 120.0,
        "light_altitude_deg": 30.0,
        "ambient": 0.28,
        "diffuse": 1.05,
        "specular": 0.12,
        "shininess": 28.0,
        "height_exaggeration": 1.4,
        "fov": 50.0,
        "auto_frame": True,
    },
    "Evening Sun": {
        "light_azimuth_deg": 225.0,
        "light_altitude_deg": 20.0,
        "ambient": 0.22,
        "diffuse": 1.1,
        "specular": 0.16,
        "shininess": 24.0,
        "height_exaggeration": 1.6,
        "fov": 55.0,
        "auto_frame": True,
    },
    "Overcast": {
        "light_azimuth_deg": 60.0,
        "light_altitude_deg": 70.0,
        "ambient": 0.45,
        "diffuse": 0.9,
        "specular": 0.04,
        "shininess": 32.0,
        "height_exaggeration": 1.2,
        "fov": 45.0,
        "auto_frame": True,
    },
    "Top-Down": {
        "light_azimuth_deg": 45.0,
        "light_altitude_deg": 75.0,
        "ambient": 0.38,
        "diffuse": 1.0,
        "specular": 0.06,
        "shininess": 26.0,
        "height_exaggeration": 1.1,
        "fov": 40.0,
        "auto_frame": True,
    },
    "Studio Soft": {
        "light_azimuth_deg": 30.0,
        "light_altitude_deg": 35.0,
        "ambient": 0.36,
        "diffuse": 1.0,
        "specular": 0.08,
        "shininess": 58.0,
        "height_exaggeration": 1.3,
        "fov": 60.0,
        "auto_frame": True,
        "light_mode": "headlight",
    },
}