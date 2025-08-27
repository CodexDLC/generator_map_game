import os

import cv2

os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"

import imageio.v2 as imageio  # <--- ИСПРАВЛЕНИЕ ЗДЕСЬ

from pathlib import Path
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

def save_control_map_exr_rf(path: Path, control_u32: np.ndarray) -> None:
    """
    Пишет control-карту Terrain3D в EXR (один канал R, FLOAT32).
    Данные берутся бит-в-бит из uint32 (биткаст в float32), как требует FORMAT_RF.
    Требуется один из бэкендов: OpenEXR+Imath или tinyexr.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if control_u32.dtype != np.uint32:
        raise TypeError("control_u32 должен быть dtype=uint32")
    if control_u32.ndim != 2:
        raise ValueError("control_u32 должен быть 2D HxW")

    img_f32 = control_u32.view(np.float32)  # биткаст без копирования
    H, W = img_f32.shape

    # Пытаемся через OpenEXR
    try:
        import OpenEXR, Imath
        header = OpenEXR.Header(W, H)
        # один канал R, тип FLOAT
        header["channels"] = {"R": Imath.Channel(Imath.PixelType(Imath.PixelType.FLOAT))}
        # необязательно, но полезно:
        header["compression"] = Imath.Compression(Imath.Compression.ZIP_COMPRESSION)
        exr = OpenEXR.OutputFile(str(path), header)
        exr.writePixels({"R": img_f32.tobytes()})
        exr.close()
        return
    except Exception:
        pass

    # Пытаемся через tinyexr
    try:
        import tinyexr
        # tinyexr ожидает список байтовых буферов на канал
        channels = [img_f32.tobytes()]  # только R
        channel_names = ["R"]
        pixel_types = [tinyexr.PixelType.FLOAT]
        tinyexr.save_image(str(path), channels, W, H, channel_names, pixel_types)
        return
    except Exception as e:
        raise RuntimeError(
            "Нет доступного бэкенда для записи EXR. "
            "Установите один из вариантов: `pip install OpenEXR Imath` или `pip install tinyexr`."
        ) from e