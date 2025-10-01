import logging
import sys
from pathlib import Path

def setup_logging():
    """
    Настраивает глобальный логгер для приложения.
    - Устанавливает формат сообщений.
    - Выводит логи в консоль (stdout).
    - Сохраняет логи в файл logs/editor.log.
    """
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "editor.log"

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s:%(lineno)d | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, mode="w", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,  # <— ВАЖНО: убирает старые хендлеры, чтобы не было дублей
    )

    # детальные логи только наших пакетов, остальное приглушим
    logging.getLogger("editor").setLevel(logging.DEBUG)
    logging.getLogger("game_engine_restructured").setLevel(logging.DEBUG)
    logging.getLogger("NodeGraphQt").setLevel(logging.WARNING)
    logging.getLogger("numba").setLevel(logging.WARNING)