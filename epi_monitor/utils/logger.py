"""
utils/logger.py
----------------
Configuração central de logging da aplicação. Grava logs tanto no console
(útil durante desenvolvimento) quanto em arquivo rotativo em
`storage/logs/`, para permitir auditoria e diagnóstico em produção.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from config.settings import settings


def configurar_logging(nivel: int = logging.INFO) -> None:
    log_dir = settings.storage.logs_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "epi_monitor.log"

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(nivel)
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Bibliotecas de terceiros tendem a ser muito verbosas; reduzimos o nível
    logging.getLogger("ultralytics").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
