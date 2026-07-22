"""
database/connection.py
-----------------------
Gerencia a engine de conexão SQLAlchemy com o PostgreSQL e fornece
sessões de banco de dados para o restante da aplicação.

Uso típico em um service:

    from database.connection import get_session

    with get_session() as session:
        camera = session.query(Camera).first()
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from config.settings import settings
from database.models import Base

# echo=settings.debug -> imprime as queries SQL no console quando DEBUG=true
engine = create_engine(
    settings.database.url,
    echo=settings.debug,
    pool_pre_ping=True,   # evita erros de "conexão caiu" em sessões longas
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    """
    Cria todas as tabelas que ainda não existem no banco.

    Em produção recomenda-se usar Alembic para migrações versionadas,
    mas para simplificar o setup inicial este método garante que o
    schema básico exista.
    """
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager que entrega uma sessão e garante commit/rollback/close."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
