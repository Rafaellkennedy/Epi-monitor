import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.security import UserService, AuthService
from models.enums import NivelAcesso
from database.models import Base

# Cria engine SQLite em memória para testes isolados
test_engine = create_engine("sqlite:///:memory:", echo=False)
TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

@pytest.fixture
def db_session():
    # Cria o esquema no SQLite
    Base.metadata.create_all(bind=test_engine)
    
    # Substitui get_session por uma versão que usa nosso test_engine
    def override_get_session():
        from contextlib import contextmanager
        @contextmanager
        def _get_session():
            session = TestingSessionLocal()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        return _get_session()
        
    with patch("core.security.get_session", side_effect=override_get_session):
        yield
        
    # Limpa as tabelas após o teste
    Base.metadata.drop_all(bind=test_engine)

def test_criar_e_autenticar_novo_usuario(db_session):
    # Cria o usuário
    user = UserService.criar_usuario("João Silva", "joaos", "joao@usina.com", "senha123", NivelAcesso.OPERADOR)
    assert user.id is not None
    assert user.nome_completo == "João Silva"
    assert user.login == "joaos"
    assert user.nivel_acesso == NivelAcesso.OPERADOR
    assert user.ativo is True
    
    # Valida login do novo usuário
    res = AuthService.autenticar("joaos", "senha123")
    assert res.sucesso is True
    assert res.usuario is not None
    assert res.usuario.id == user.id

def test_alternar_status_usuario(db_session):
    # Cria o usuário
    user = UserService.criar_usuario("Maria Souza", "marias", "maria@usina.com", "senha123", NivelAcesso.OPERADOR)
    
    # Inativa o usuário
    novo_status = UserService.alternar_status(user.id)
    assert novo_status is False
    
    # Tenta autenticar (deve falhar pois está inativo)
    res = AuthService.autenticar("marias", "senha123")
    assert res.sucesso is False
    assert "desativado" in res.mensagem.lower()
    
    # Ativa novamente
    novo_status = UserService.alternar_status(user.id)
    assert novo_status is True
    
    # Tenta autenticar (deve ter sucesso)
    res = AuthService.autenticar("marias", "senha123")
    assert res.sucesso is True

def test_redefinir_senha(db_session):
    # Cria o usuário
    user = UserService.criar_usuario("Pedro Silva", "pedros", "pedro@usina.com", "senha123", NivelAcesso.OPERADOR)
    
    # Tenta autenticar com a senha antiga
    res = AuthService.autenticar("pedros", "senha123")
    assert res.sucesso is True
    
    # Redefine a senha
    UserService.redefinir_senha(user.id, "nova_senha456")
    
    # Tenta autenticar com a senha antiga (deve falhar)
    res_falha = AuthService.autenticar("pedros", "senha123")
    assert res_falha.sucesso is False
    
    # Tenta autenticar com a nova senha
    res_sucesso = AuthService.autenticar("pedros", "nova_senha456")
    assert res_sucesso.sucesso is True
