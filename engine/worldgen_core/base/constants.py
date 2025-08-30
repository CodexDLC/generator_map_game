from typing import Dict

KIND_GROUND = "ground"
KIND_OBSTACLE = "obstacle"
KIND_WATER = "water"
KIND_ROAD = "road"
KIND_VOID = "void"
KIND_VALUES = (KIND_GROUND, KIND_OBSTACLE, KIND_WATER, KIND_VOID)

# <<< НОВЫЙ БЛОК: Централизованные маппинги >>>
# Используем для кодирования в RLE и рендеринга
KIND_TO_ID: Dict[str, int] = {
    KIND_GROUND: 0,
    KIND_OBSTACLE: 1,
    KIND_WATER: 2,
    KIND_ROAD: 3,
    KIND_VOID: 4,
}

ID_TO_KIND: Dict[int, str] = {v: k for k, v in KIND_TO_ID.items()}
# <<< КОНЕЦ НОВОГО БЛОКА >>>

DEFAULT_PALETTE: Dict[str, str] = {
    KIND_GROUND: "#7a9e7a",
    KIND_OBSTACLE: "#444444",
    KIND_WATER: "#3573b8",
    KIND_VOID: "#00000000",
}


