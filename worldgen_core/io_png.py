from pathlib import Path
import imageio.v2 as imageio
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
    if arr.dtype != np.uint16:  # на всякий случай
        arr = arr.astype(np.uint16)
    return arr
