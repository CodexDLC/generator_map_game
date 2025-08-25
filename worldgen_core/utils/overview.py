import math

import numpy as np
import imageio.v2 as imageio
from pathlib import Path

try:
    import cv2
except ImportError:
    cv2 = None


# Эта функция была перемещена из pipeline.py, поэтому её импорт нужно добавить.
def _stitch_height(base: Path, width: int, height: int, chunk: int) -> np.ndarray:
    """Собрать весь мир в uint16 из сохранённых чанков."""
    canvas = np.zeros((height, width), dtype=np.uint16)
    hdir = base / "height"
    ny, nx = math.ceil(height / chunk), math.ceil(width / chunk)
    for j in range(ny):
        for i in range(nx):
            p = hdir / f"chunk_{i}_{j}.png"
            if not p.exists(): continue
            tile = imageio.imread(p.as_posix())
            h, w = tile.shape[0], tile.shape[1]
            y0, x0 = j * chunk, i * chunk
            canvas[y0:y0 + h, x0:x0 + w] = tile
    return canvas


def _build_overview(base: Path, cfg, out_px: int):
    """Создает уменьшенное 8-битное превью всей карты."""
    full_heightmap = _stitch_height(base, cfg.width, cfg.height, cfg.chunk)
    overview_map_8bit = None

    if cv2:
        try:
            scale_factor = out_px / float(max(full_heightmap.shape))
            resized_map = cv2.resize(
                full_heightmap,
                (int(full_heightmap.shape[1] * scale_factor), int(full_heightmap.shape[0] * scale_factor)),
                interpolation=cv2.INTER_AREA
            )
            overview_map_8bit = np.right_shift(resized_map, 8).astype(np.uint8)
        except cv2.error as e:
            # Теперь мы явно ловим ошибку от cv2, если она возникнет.
            print(f"Ошибка при использовании OpenCV: {e}. Переключаюсь на простой метод.")
        except Exception:
            # Если cv2 не справился, используем простой метод
            pass

    if overview_map_8bit is None:
        # Простой даунсемплинг без cv2 или если cv2 выдал ошибку
        step = max(1, max(full_heightmap.shape) // out_px)
        overview_map_8bit = np.right_shift(full_heightmap[::step, ::step], 8).astype(np.uint8)

    (base / "overview").mkdir(exist_ok=True)
    imageio.imwrite((base / "overview" / f"height_overview_{out_px}.png").as_posix(), overview_map_8bit)