from pathlib import Path
import json


def generate_scatter_map(world_path: Path, rules: list):
    """
    Основная функция для генерации карты размещения объектов.
    """
    print(f"Запущена генерация карты объектов для мира: {world_path}")
    print(f"Используется {len(rules)} правил.")

    scatter_data = {
        "rules_used": rules,
        "objects": []  # Список объектов пока будет пустым
    }

    out_path = world_path / "scatter_map.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(scatter_data, f, indent=2, ensure_ascii=False)

    return str(out_path.resolve())