from __future__ import annotations
import json, pathlib
from typing import Any, Dict, Optional
from engine.worldgen_core.base.preset import Preset, DEFAULT_PALETTE
from engine.worldgen_core.base.export import write_chunk_rle_json, write_chunk_meta_json, write_preview_png
from engine.worldgen_core.world.world_generator import WorldGenerator

ART_ROOT = pathlib.Path("artifacts") / "world"

def ensure_dir(p: pathlib.Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _load_preset_optional(preset_path: pathlib.Path) -> Optional[Preset]:
    """
    Пытаемся загрузить пресет, но если у Preset нет нужного метода — возвращаем None.
    Генератор и экспорт умеют работать с дефолтами без пресета.
    """
    try:
        P = Preset  # alias
        path_str = str(preset_path)
        # Популярные варианты API:
        if hasattr(P, "from_json_path"):
            return P.from_json_path(path_str)               # твой вариант?
        if hasattr(P, "from_file"):
            return P.from_file(path_str)
        if hasattr(P, "from_path"):
            return P.from_path(path_str)
        # Пробуем вручную распарсить и скормить Preset
        with open(preset_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if hasattr(P, "from_json"):
            return P.from_json(data)
        if hasattr(P, "from_dict"):
            return P.from_dict(data)
        try:
            # На крайний случай попробуем конструктор
            return P(**data)  # type: ignore[arg-type]
        except Exception:
            return None
    except Exception:
        return None


def generate_or_load(seed: int, cx: int, cz: int, preset_path: pathlib.Path, world_id: str = "city") -> Dict[str, Any]:
    """
    Сгенерировать или загрузить чанк.
    Город (city @ 0,0) теперь считается статичным и загружается из /city/static/.
    """
    # Особая обработка статичного города
    if world_id == "city" and cx == 0 and cz == 0:
        # ... (эта часть кода без изменений) ...
        static_city_dir = ART_ROOT / "city" / "static" / "0_0"
        rle_path = static_city_dir / "chunk.rle.json"
        meta_path = static_city_dir / "chunk.meta.json"
        print(f"--- WORLDGEN: Загрузка статичного города из: {static_city_dir}")
        if not rle_path.exists() or not meta_path.exists():
            print("!!! LOG: Файлы для статичного города не найдены. Создана пустая карта.")
            return {"layers": {"kind": [["ground"] * 128] * 128}, "ports": {}}  # Увеличил размер заглушки
        with open(rle_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        data["_meta"] = meta
        return data

    # Логика для процедурной генерации
    world_parts = world_id.split('/')
    out_dir = ART_ROOT.joinpath(*world_parts) / str(seed) / f"{cx}_{cz}"
    ensure_dir(out_dir)

    rle_path = out_dir / "chunk.rle.json"
    meta_path = out_dir / "chunk.meta.json"

    # Проверка кэша
    if rle_path.exists() and meta_path.exists():
        print(f"--- WORLDGEN: Чанк найден в {out_dir}, загрузка с диска.")
        with open(rle_path, "r", encoding="utf-8") as f: data = json.load(f)
        with open(meta_path, "r", encoding="utf-8") as f: meta = json.load(f)
        data["_meta"] = meta
        return data

    print(f"--- WORLDGEN: Чанк не найден, запуск новой генерации для {out_dir}.")
    preset = _load_preset_optional(preset_path)

    gen_params = {"seed": seed, "cx": cx, "cz": cz, "world_id": world_id}
    if world_id.startswith("branch/"):
        gen_params["branch_bias"] = 0.25

    # <<< ВАЖНО: ВЫЗЫВАЕМ ПРАВИЛЬНЫЙ КЛАСС >>>
    gen = WorldGenerator(preset=preset)
    res = gen.generate(gen_params)

    print("--- WORLDGEN: Генерация завершена. Сохранение файлов...")
    write_chunk_rle_json(str(rle_path), res.layers["kind"], res.size, seed, cx, cz)
    write_chunk_meta_json(str(meta_path), {
        "version": "1.0", "type": "chunk_meta", "seed": seed, "size": res.size, "cx": cx, "cz": cz,
        "edges": res.metrics.get("edges", {}), "ports": res.ports,  # Используем res.ports
        "metrics": res.metrics,
        "world_id": world_id
    })

    palette = (getattr(preset, "export", {}).get("palette", DEFAULT_PALETTE) if preset else DEFAULT_PALETTE)
    write_preview_png(str(out_dir / "preview.png"), res.layers["kind"], palette, res.ports)

    # Формируем итоговый объект для возврата в UI
    data = {
        "version": res.version, "type": res.type, "seed": res.seed, "size": res.size,
        "layers": res.layers, "ports": res.ports,
        "_meta": {"world_id": world_id, "edges": res.metrics.get("edges", {}), "ports": res.ports}
    }
    return data
