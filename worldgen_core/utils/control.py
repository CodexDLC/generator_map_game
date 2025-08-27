import numpy as np


def build_control_uint32(biome_ids_u8: np.ndarray, mapping: dict[int, int] | None = None) -> np.ndarray:
    """
    Возвращает HxW uint32 по формату Terrain3D:
    base[32..28], overlay[27..23], blend[22..15], uv_angle[14..11],
    uv_scale[10..8], hole[3], nav[2], auto[1].
    """
    # biome -> индекс текстуры (0..31)
    if mapping:
        base_id = np.zeros_like(biome_ids_u8, dtype=np.uint32)
        for b, tex in mapping.items():
            base_id[biome_ids_u8 == b] = np.uint32(tex & 31)
    else:
        base_id = (biome_ids_u8.astype(np.uint32) & 31)

    overlay  = np.zeros_like(base_id, dtype=np.uint32)      # нет оверлея
    blend    = np.zeros_like(base_id, dtype=np.uint32)      # 0 = только base (255 = 100% overlay)
    uv_angle = np.zeros_like(base_id, dtype=np.uint32)      # 0..15
    uv_scale = np.zeros_like(base_id, dtype=np.uint32)      # 0..7
    hole     = np.zeros_like(base_id, dtype=np.uint32)      # 0/1
    nav      = np.ones_like (base_id, dtype=np.uint32)      # 1 = можно ходить
    auto     = np.zeros_like(base_id, dtype=np.uint32)      # 0 = manual (не автошейдер)

    ctrl = ((base_id & 0x1F) << 27) \
         | ((overlay & 0x1F) << 22) \
         | ((blend   & 0xFF) << 14) \
         | ((uv_angle & 0x0F) << 10) \
         | ((uv_scale & 0x07) << 7)  \
         | ((hole    & 0x01) << 2)   \
         | ((nav     & 0x01) << 1)   \
         |  (auto    & 0x01)
    return ctrl