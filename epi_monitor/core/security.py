"""
core/security.py
-----------------
Funções e serviço de autenticação/segurança:
    - hash_password / verify_password: criptografia de senhas com bcrypt
    - AuthService: login com controle de tentativas falhas e bloqueio temporário
    - controle de níveis de acesso (RBAC simples)

Nenhuma senha é armazenada em texto plano em nenhum momento.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Optional

import bcrypt

from config.settings import settings
from database.connection import get_session
from database.models import Usuario, Log, NivelLog
from models.enums import NivelAcesso


# --------------------------------------------------------------------------
# Hashing de senha
# --------------------------------------------------------------------------
def hash_password(plain_password: str) -> str:
    """Gera um hash bcrypt seguro (com salt automático) para a senha."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verifica se a senha em texto plano corresponde ao hash armazenado."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # hash inválido/corrompido
        return False


# --------------------------------------------------------------------------
# Resultado de autenticação
# --------------------------------------------------------------------------
@dataclass
class AuthResult:
    sucesso: bool
    mensagem: str
    usuario: Optional[Usuario] = None


class AuthService:
    """Serviço responsável por autenticar usuários e aplicar políticas de segurança."""

    @staticmethod
    def autenticar(login: str, senha: str) -> AuthResult:
        with get_session() as session:
            usuario = session.query(Usuario).filter_by(login=login).first()

            if usuario is None:
                AuthService._registrar_log(session, None, NivelLog.AVISO, "auth",
                                            f"Tentativa de login com usuário inexistente: '{login}'")
                return AuthResult(False, "Usuário ou senha inválidos.")

            # Verifica bloqueio temporário por excesso de tentativas
            if usuario.bloqueado_ate and usuario.bloqueado_ate > datetime.datetime.now(datetime.timezone.utc):
                minutos_restantes = int(
                    (usuario.bloqueado_ate - datetime.datetime.now(datetime.timezone.utc)).total_seconds() / 60
                ) + 1
                return AuthResult(False, f"Conta bloqueada. Tente novamente em {minutos_restantes} minuto(s).")

            if not usuario.ativo:
                return AuthResult(False, "Usuário desativado. Contate o administrador.")

            if not verify_password(senha, usuario.senha_hash):
                usuario.tentativas_login_falhas += 1
                if usuario.tentativas_login_falhas >= settings.security.max_login_attempts:
                    usuario.bloqueado_ate = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
                        minutes=settings.security.lockout_minutes
                    )
                    AuthService._registrar_log(
                        session, usuario.id, NivelLog.AVISO, "auth",
                        f"Usuário '{login}' bloqueado por {settings.security.lockout_minutes} min "
                        f"após {usuario.tentativas_login_falhas} tentativas falhas."
                    )
                session.commit()
                return AuthResult(False, "Usuário ou senha inválidos.")

            # Login com sucesso: reseta contadores e registra
            usuario.tentativas_login_falhas = 0
            usuario.bloqueado_ate = None
            usuario.ultimo_login = datetime.datetime.now(datetime.timezone.utc)
            AuthService._registrar_log(session, usuario.id, NivelLog.INFO, "auth",
                                        f"Login bem-sucedido: '{login}'")
            session.commit()
            session.refresh(usuario)
            # Expunge para poder usar o objeto fora da sessão (ex.: na UI)
            session.expunge(usuario)
            return AuthResult(True, "Login realizado com sucesso.", usuario)

    @staticmethod
    def _registrar_log(session, usuario_id: Optional[int], nivel: NivelLog, origem: str, mensagem: str) -> None:
        session.add(Log(usuario_id=usuario_id, nivel=nivel, origem=origem, mensagem=mensagem))


# --------------------------------------------------------------------------
# Controle de acesso (RBAC simples baseado em hierarquia)
# --------------------------------------------------------------------------
_HIERARQUIA = {
    NivelAcesso.OPERADOR: 1,
    NivelAcesso.TECNICO_SEGURANCA: 2,
    NivelAcesso.ADMINISTRADOR: 3,
}


def possui_permissao(nivel_usuario: NivelAcesso, nivel_minimo_exigido: NivelAcesso) -> bool:
    """Retorna True se o nível do usuário é igual ou superior ao exigido."""
    return _HIERARQUIA.get(nivel_usuario, 0) >= _HIERARQUIA.get(nivel_minimo_exigido, 0)


# --------------------------------------------------------------------------
# Serviço de Usuários (CRUD e Gestão)
# --------------------------------------------------------------------------
class UserService:
    """Serviço para gestão e administração de contas de usuário (CRUD)."""

    @staticmethod
    def criar_usuario(nome_completo: str, login: str, email: str, senha_plana: str, nivel: NivelAcesso) -> Usuario:
        with get_session() as session:
            novo = Usuario(
                nome_completo=nome_completo,
                login=login,
                email=email,
                senha_hash=hash_password(senha_plana),
                nivel_acesso=nivel,
                ativo=True
            )
            session.add(novo)
            session.commit()
            session.refresh(novo)
            session.expunge(novo)
            return novo

    @staticmethod
    def alternar_status(usuario_id: int) -> bool:
        """Ativa/Desativa um usuário."""
        with get_session() as session:
            usr = session.get(Usuario, usuario_id)
            if usr:
                usr.ativo = not usr.ativo
                session.commit()
                return usr.ativo
            return False

    @staticmethod
    def redefinir_senha(usuario_id: int, nova_senha_plana: str) -> bool:
        """Redefine a senha de um usuário."""
        with get_session() as session:
            usr = session.get(Usuario, usuario_id)
            if usr:
                usr.senha_hash = hash_password(nova_senha_plana)
                session.commit()
                return True
            return False
