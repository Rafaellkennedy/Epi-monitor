"""
scripts/setup_database.py
----------------------------
Script utilitário de linha de comando para preparar o ambiente antes do
primeiro uso do EPI Monitor:
    1. Cria o banco de dados PostgreSQL (se ainda não existir).
    2. Cria todas as tabelas (init_db).
    3. Popula dados iniciais (usuário admin + configurações padrão).

Uso:
    python scripts/setup_database.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from config.settings import settings


def criar_banco_se_nao_existir() -> None:
    """Conecta ao banco 'postgres' padrão para criar o banco da aplicação."""
    db = settings.database
    conn = psycopg2.connect(
        host=db.host, port=db.port, user=db.user, password=db.password, dbname="postgres"
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db.name,))
    existe = cursor.fetchone()

    if not existe:
        cursor.execute(f'CREATE DATABASE "{db.name}"')
        print(f"[setup] Banco de dados '{db.name}' criado com sucesso.")
    else:
        print(f"[setup] Banco de dados '{db.name}' já existe. Prosseguindo.")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    print("[setup] Verificando/criando banco de dados PostgreSQL...")
    criar_banco_se_nao_existir()

    from database.connection import init_db
    from database.seed import run_seed

    print("[setup] Criando tabelas...")
    init_db()

    print("[setup] Populando dados iniciais...")
    run_seed()

    print("\n[setup] Ambiente pronto! Execute a aplicação com: python -m app.main")
    print("[setup] Login padrão -> usuário: admin | senha: admin123 (altere no primeiro acesso)")
