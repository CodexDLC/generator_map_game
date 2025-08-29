from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class WorldState:
    # Городской сид — базовый для всех веток
    city_seed: int = 123

    # Текущий активный сид мира (в городе = city_seed; в ветви = branch_seed)
    seed: int = 123

    # Координаты текущего мира
    cx: int = 0
    cz: int = 0

    # Пресет
    preset_path: str = "engine/presets/world/base_default.json"

    # Текущий мир: "city" | "branch/E" | "branch/W" | ...
    world_id: str = "city"

    # Кэш чанков по ключу (cx,cz,seed,world_id,ver)
    cache: dict = field(default_factory=dict)

    def __post_init__(self):
        # при старте в городе всегда seed = city_seed
        self.seed = int(self.city_seed)

    def key(self) -> tuple[int, int, int, str, int]:
        return (self.cx, self.cz, int(self.seed), str(self.world_id), 1)
