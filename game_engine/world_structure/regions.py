# game_engine/world_structure/regions.py
from dataclasses import dataclass, field
from typing import Dict, Tuple, List, Any
from pathlib import Path

from .road_types import ChunkRoadPlan
from ..core.preset import Preset
from ..core.types import GenResult
from ..core.export import write_region_meta, write_client_chunk, write_chunk_preview
from .serialization import RegionMetaContract, ClientChunkContract
from ..generators._base.generator import BaseGenerator
from ..generators.world.world_generator import WorldGenerator

# --- Функции для работы с сеткой регионов (остаются без изменений) ---
REGION_SIZE = 7
REGION_OFFSET = REGION_SIZE // 2


def region_key(cx: int, cz: int) -> Tuple[int, int]:
    scx = (cx + REGION_OFFSET) // REGION_SIZE if cx >= -REGION_OFFSET else (cx - REGION_OFFSET) // REGION_SIZE
    scz = (cz + REGION_OFFSET) // REGION_SIZE if cz >= -REGION_OFFSET else (cz - REGION_OFFSET) // REGION_SIZE
    return scx, scz


def region_base(scx: int, scz: int) -> Tuple[int, int]:
    base_cx = scx * REGION_SIZE - REGION_OFFSET
    base_cz = scz * REGION_SIZE - REGION_OFFSET
    return base_cx, base_cz


@dataclass
class Region:
    """Внутреннее представление региона в памяти."""
    scx: int
    scz: int
    road_plan: Dict[Tuple[int, int], ChunkRoadPlan] = field(default_factory=dict)
    final_chunks: Dict[Tuple[int, int], GenResult] = field(default_factory=dict)


# --- НОВЫЙ REGION MANAGER ---
class RegionManager:
    def __init__(self, world_seed: int, preset: Preset, base_generator: BaseGenerator, world_generator: WorldGenerator,
                 artifacts_root: Path):
        self.world_seed = world_seed
        self.preset = preset
        self.region_cache: Dict[Tuple[int, int], Region] = {}
        self.base_generator = base_generator
        self.world_generator = world_generator
        self.artifacts_root = artifacts_root

    def _get_region_path(self, scx: int, scz: int) -> Path:
        """Определяет путь к папке региона."""
        return self.artifacts_root / "world" / "world_location" / str(self.world_seed) / "regions" / f"{scx}_{scz}"

    def ensure_region_is_generated(self, cx: int, cz: int):
        """
        Главный метод. Проверяет, сгенерирован ли регион на диске.
        Если нет - запускает полный процесс генерации.
        """
        scx, scz = region_key(cx, cz)
        region_path = self._get_region_path(scx, scz)
        meta_path = region_path / "region_meta.json"

        if meta_path.exists():
            # Регион уже сгенерирован, ничего не делаем
            return

        self._generate_full_region(scx, scz, region_path)

    def _generate_full_region(self, scx: int, scz: int, region_path: Path):
        print(f"[RegionManager] Starting full generation for region ({scx}, {scz})...")
        base_cx, base_cz = region_base(scx, scz)

        # --- ПРОХОД 1: ГЕНЕРАЦИЯ "ГОЛОГО" ЛАНДШАФТА ---
        print("[RegionManager] Pass 1: Generating base landscape for 49 chunks...")
        base_chunks: Dict[Tuple[int, int], GenResult] = {}
        for dz in range(REGION_SIZE):
            for dx in range(REGION_SIZE):
                cx, cz = base_cx + dx, base_cz + dz
                params = {"seed": self.world_seed, "cx": cx, "cz": cz}
                base_chunks[(cx, cz)] = self.base_generator.generate(params)

        # --- ПРОХОД 2: ГЛОБАЛЬНОЕ ПЛАНИРОВАНИЕ ---
        from .planners.road_planner import plan_roads_for_region
        print("[RegionManager] Pass 2: Planning global roads...")
        road_plan = plan_roads_for_region(scx, scz, self.world_seed, self.preset, base_chunks)

        # --- ПРОХОД 3: ФИНАЛЬНАЯ ДЕТАЛИЗАЦИЯ И СОХРАНЕНИЕ ---
        print("[RegionManager] Pass 3: Finalizing and exporting 49 chunks...")
        new_region = Region(scx=scx, scz=scz, road_plan=road_plan)

        for (cx, cz), base_chunk in base_chunks.items():
            final_chunk = self.world_generator.finalize_chunk(base_chunk, new_region)
            new_region.final_chunks[(cx, cz)] = final_chunk

            # Сохраняем клиентский чанк
            client_contract = ClientChunkContract(cx=cx, cz=cz, layers=final_chunk.layers)
            chunk_path = region_path / "chunks" / f"{cx}_{cz}.json"
            write_client_chunk(str(chunk_path), client_contract)

            # Сохраняем превью для миникарты
            preview_path = region_path / "previews" / f"{cx}_{cz}.png"
            palette = self.preset.export.get("palette", {})
            write_chunk_preview(str(preview_path), final_chunk.layers["kind"], palette)

        # Сохраняем метаданные региона
        meta_contract = RegionMetaContract(scx=scx, scz=scz, world_seed=self.world_seed, road_plan=road_plan)
        write_region_meta(str(region_path / "region_meta.json"), meta_contract)

        print(f"[RegionManager] Region ({scx}, {scz}) generation complete.")