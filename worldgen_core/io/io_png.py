# io_png.py
from pathlib import Path
import numpy as np
import imageio.v2 as imageio


def save_png16(path: Path, data_u16: np.ndarray) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if data_u16.dtype != np.uint16:
        data_u16 = data_u16.astype(np.uint16, copy=False)
    imageio.imwrite(path.as_posix(), data_u16)


def save_biome_png(path: Path, biome_u8: np.ndarray, palette: np.ndarray) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if biome_u8.dtype != np.uint8:
        biome_u8 = biome_u8.astype(np.uint8, copy=False)
    rgb = palette[biome_u8]
    imageio.imwrite(path.as_posix(), rgb)


def load_png16(path: Path) -> np.ndarray:
    arr = imageio.imread(Path(path).as_posix())
    if arr.dtype != np.uint16:
        arr = arr.astype(np.uint16, copy=False)
    return arr


def save_raw16(path: Path, data_u16: np.ndarray) -> None:
    """R16 «сырым» для Terrain3D (без заголовка)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if data_u16.dtype != np.uint16:
        data_u16 = data_u16.astype(np.uint16, copy=False)
    data_u16.tofile(path)


def save_control_map_exr_rf(path: Path, control_u32: np.ndarray) -> None:
    """
    EXR (FORMAT_RF): один канал R, float32.
    Пишем бит-в-бит: uint32 -> view(float32), без конверсии значений.
    Бэкенды: OpenEXR -> imageio FreeImage.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if control_u32.dtype != np.uint32 or control_u32.ndim != 2:
        raise TypeError("control_u32 должен быть 2D и dtype=uint32")

    img_f32 = control_u32.view(np.float32)
    H, W = img_f32.shape

    # 1) OpenEXR (+Imath)
    try:
        import OpenEXR, Imath
        header = OpenEXR.Header(W, H)
        header["channels"] = {"R": Imath.Channel(Imath.PixelType(Imath.PixelType.FLOAT))}
        # опционально: сжатие
        try:
            header["compression"] = Imath.Compression(Imath.Compression.ZIP_COMPRESSION)
        except Exception:
            pass
        out = OpenEXR.OutputFile(str(path), header)
        out.writePixels({"R": img_f32.tobytes()})
        out.close()
        return
    except Exception:
        pass

    # 2) imageio + FreeImage (EXR-FI)
    try:
        # попробуем подтянуть бинарник FreeImage (если ещё не скачан)
        try:
            import imageio.plugins.freeimage as fi
            fi.download()  # no-op если уже есть
        except Exception:
            pass
        imageio.imwrite(path.as_posix(), img_f32, format="EXR-FI")
        return
    except Exception as e:
        raise RuntimeError(
            "Не удалось сохранить EXR: нет доступных бэкендов (OpenEXR или imageio FreeImage). "
            "Решение: либо установите `pip install OpenEXR Imath` (желательно Python 3.11), "
            "либо используйте imageio с FreeImage (см. логи)."
        ) from e


def save_temperature_png(path: Path, temp_C: np.ndarray,
                         tmin: float = -30.0, tmax: float = 40.0) -> None:
    """
    Сохраняет температуру (°C) как серый PNG16.
    Диапазон tmin..tmax линеаризуется в 0..65535.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    t = np.clip((temp_C.astype(np.float32) - tmin) / (tmax - tmin), 0.0, 1.0)
    img = (t * 65535.0 + 0.5).astype(np.uint16)
    imageio.imwrite(path.as_posix(), img)