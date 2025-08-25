from pathlib import Path
import imageio.v2 as imageio  # <--- ИСПРАВЛЕНИЕ ЗДЕСЬ
import numpy as np

def save_png16(path: Path, data_u16: np.ndarray):
    path.parent.mkdir(parents=True, exist_ok=True)
    imageio.imwrite(path.as_posix(), data_u16)

def save_biome_png(path: Path, biome_u8: np.ndarray, palette):
    rgb = palette[biome_u8]
    path.parent.mkdir(parents=True, exist_ok=True)
    imageio.imwrite(path.as_posix(), rgb)

def load_png16(path: Path) -> np.ndarray:
    arr = imageio.imread(path.as_posix())
    if arr.dtype != np.uint16:
        arr = arr.astype(np.uint16)
    return arr

def save_raw16(path: Path, data_u16: np.ndarray):
    """ Сохраняет карту высот в сыром 16-битном формате (R16) для Terrain3D. """
    path.parent.mkdir(parents=True, exist_ok=True)
    data_u16.tofile(path)

def save_control_map_r32(path: Path, biome_u8: np.ndarray):
    """
    Сохраняет карту биомов в формат ControlMap для Terrain3D.
    Пока что мы записываем только ID базовой текстуры.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    control_map = (biome_u8.astype(np.uint32) & 0x1F) << 27
    control_map.tofile(path)