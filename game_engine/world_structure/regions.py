from dataclasses import dataclass, field
from typing import Dict, Tuple, List

# === Суперчанки (регионы) ===
REGION_SIZE = 7  # сторона региона в обычных чанках (нечётное число)

def region_key(cx: int, cz: int) -> Tuple[int, int]:
    """Ключ региона (scx, scz) по координатам чанка."""
    return (cx // REGION_SIZE, cz // REGION_SIZE)

def region_base(scx: int, scz: int) -> Tuple[int, int]:
    """Левый-верхний чанк региона (base_cx, base_cz)."""
    return (scx * REGION_SIZE, scz * REGION_SIZE)

@dataclass
class Region:
    """Метаданные одного региона (суперчанка)."""
    scx: int
    scz: int
    biome_type: str = "dense_forest"
    difficulty: float = 1.0
    # ключ = (cx,cz) обычного чанка; значение = список сторон дорог ['N','E','S','W']
    road_plan: Dict[Tuple[int, int], List[str]] = field(default_factory=dict)

class RegionManager:
    """Кэш регионов. Ключ = (scx,scz)."""
    def __init__(self, world_seed: int, region_size: int = REGION_SIZE):
        if region_size % 2 == 0:
            raise ValueError("region_size должен быть нечётным (3,5,7,...)")
        self.world_seed = world_seed
        self.region_size = region_size
        self.cache: Dict[Tuple[int, int], Region] = {}

    def get_region(self, cx: int, cz: int) -> Region:
        scx, scz = region_key(cx, cz)
        key = (scx, scz)
        reg = self.cache.get(key)
        if reg:
            return reg

        base_cx, base_cz = region_base(scx, scz)
        reg = Region(scx=scx, scz=scz)

        # ленивые импорты, чтобы избежать циклов
        from .planners.biome_planner import assign_biome_to_region
        from .planners.road_planner import plan_roads_for_region

        reg.biome_type = assign_biome_to_region(self.world_seed, scx, scz)
        reg.road_plan = plan_roads_for_region(reg, self.world_seed)

        self.cache[key] = reg
        print(f"[RegionManager] New region key={key} base=({base_cx},{base_cz}) size={self.region_size}")
        return reg
