# Использование

## Запуск тестера

1. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

2. Запустите визуализатор:
   ```bash
   python run_pygame_tester.py
   ```

## Генерация мира
- Все параметры генерации задаются через пресеты (`game_engine/core/preset/defaults.py`)
- Для изменения логики генерации используйте генераторы в `game_engine/generators/`
