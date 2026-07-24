import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# Adiciona o diretório raiz do projeto ao sys.path para importar os modelos
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings
from database.models import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

# Configura dynamic DB URL vindo das settings (.env)
config.set_main_option("sqlalchemy.url", settings.database.url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Roda migrações no modo 'offline' sem criar conexão de engine real."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Roda migrações no modo 'online' criando conexão com o banco de dados."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
