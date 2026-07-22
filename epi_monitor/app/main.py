"""
app/main.py
-----------
Ponto de entrada da aplicação EPI Monitor.

Fluxo de inicialização:
    1. Configura logging.
    2. Garante que o schema do banco de dados existe (init_db) e popula
       dados iniciais (seed) na primeira execução.
    3. Aplica o tema visual (dark/light).
    4. Exibe a tela de Login.
    5. Após autenticação bem-sucedida, abre a MainWindow e inicia o
       monitoramento das câmeras cadastradas.

Para rodar em desenvolvimento:
    python -m app.main
"""

from __future__ import annotations

import sys
import logging

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt

# Garante que o diretório raiz do projeto está no sys.path quando executado
# diretamente (python app/main.py) e não apenas como módulo (-m app.main).
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.logger import configurar_logging
from database.connection import init_db
from database.seed import run_seed
from config.settings import settings
from ui.theme import apply_theme
from ui.login_window import LoginWindow
from ui.main_window import MainWindow

logger = logging.getLogger(__name__)


def inicializar_infraestrutura() -> None:
    """Prepara banco de dados e diretórios de armazenamento antes da UI subir."""
    configurar_logging()
    logger.info("Iniciando EPI Monitor...")

    try:
        init_db()
        run_seed()
        logger.info("Banco de dados inicializado com sucesso.")
    except Exception as e:
        logger.exception("Falha crítica ao conectar/inicializar o banco de dados.")
        QMessageBox.critical(
            None, "Erro de Banco de Dados",
            f"Não foi possível conectar ao PostgreSQL.\n\n"
            f"Verifique as configurações em '.env' (DB_HOST, DB_PORT, DB_NAME, "
            f"DB_USER, DB_PASSWORD) e se o serviço do PostgreSQL está em execução.\n\n"
            f"Detalhes técnicos: {e}"
        )
        sys.exit(1)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(settings.ui.app_name)
    app.setOrganizationName(settings.ui.org_name)
    apply_theme(app, settings.ui.default_theme)

    inicializar_infraestrutura()

    # Mantém referência da MainWindow no escopo externo para não ser
    # coletada pelo garbage collector após o fechamento do LoginWindow.
    janela_principal: dict[str, MainWindow] = {}

    login_window = LoginWindow()
    apply_theme(app, settings.ui.default_theme)

    def _ao_logar(usuario) -> None:
        logger.info(f"Usuário '{usuario.login}' autenticado. Abrindo aplicação principal.")
        main_window = MainWindow(usuario, app)
        janela_principal["ref"] = main_window
        main_window.showMaximized()
        main_window.iniciar_monitoramento()
        login_window.close()

    login_window.login_sucesso.connect(_ao_logar)
    login_window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
