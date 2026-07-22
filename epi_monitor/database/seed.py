"""
database/seed.py
-----------------
Popula o banco com dados iniciais indispensáveis para o primeiro uso:
    - Usuário administrador padrão (login: admin / senha: admin123)
    - Configurações padrão do sistema

Executar uma vez após `init_db()`, por exemplo no primeiro start da aplicação.
IMPORTANTE: o usuário deve trocar a senha padrão no primeiro acesso.
"""

from __future__ import annotations

from database.connection import get_session
from database.models import Usuario, Configuracao
from models.enums import NivelAcesso
from core.security import hash_password


DEFAULT_CONFIGS = {
    "tema_padrao": ("dark", "Tema padrão da interface (dark/light)"),
    "email_alertas_ativo": ("false", "Enviar alertas por e-mail"),
    "som_alertas_ativo": ("true", "Tocar som ao detectar infração"),
    "cooldown_alerta_segundos": ("30", "Intervalo mínimo entre alertas repetidos da mesma câmera"),
    "retencao_evidencias_dias": ("90", "Dias de retenção de fotos/vídeos de infração"),
}


def run_seed() -> None:
    with get_session() as session:
        # Usuário admin padrão
        existing = session.query(Usuario).filter_by(login="admin").first()
        if not existing:
            admin = Usuario(
                nome_completo="Administrador do Sistema",
                login="admin",
                email="admin@empresa.com",
                senha_hash=hash_password("admin123"),
                nivel_acesso=NivelAcesso.ADMINISTRADOR,
                ativo=True,
            )
            session.add(admin)
            print("[seed] Usuário administrador padrão criado (admin / admin123). "
                  "ALTERE A SENHA no primeiro acesso.")

        # Configurações padrão
        for chave, (valor, descricao) in DEFAULT_CONFIGS.items():
            existente = session.query(Configuracao).filter_by(chave=chave).first()
            if not existente:
                session.add(Configuracao(chave=chave, valor=valor, descricao=descricao))

        session.commit()


if __name__ == "__main__":
    from database.connection import init_db
    init_db()
    run_seed()
    print("[seed] Banco de dados inicializado com sucesso.")
