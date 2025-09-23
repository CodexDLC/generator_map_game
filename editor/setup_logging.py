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
        format="[%(asctime)s] - [%(levelname)s] - [%(name)s] - %(message)s",
        handlers=[
            logging.FileHandler(log_file, mode='w', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info("="*50)
    logging.info("Logger configured successfully.")
    logging.info("="*50)