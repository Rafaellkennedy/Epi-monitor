"""
database/models.py
-------------------
Entidades ORM (SQLAlchemy 2.x) que mapeiam as tabelas do PostgreSQL.

Tabelas implementadas (conforme especificação):
    - usuarios
    - cameras
    - camera_epis (associação N:N câmera <-> EPI obrigatório)
    - eventos
    - alertas
    - configuracoes
    - logs

Usamos o estilo "Declarative Mapped" do SQLAlchemy 2.0, com type hints,
o que dá autocomplete e checagem estática melhores que o estilo antigo.
"""

from __future__ import annotations

import datetime
import enum
from typing import Optional, List

from sqlalchemy import (
    String, Integer, Boolean, DateTime, ForeignKey, Float, Text,
    Enum as SAEnum, UniqueConstraint, Index, func
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship
)

from models.enums import (
    NivelAcesso, ProtocoloCamera, StatusCamera, TipoEPI,
    TipoEvento, SeveridadeAlerta, StatusAlerta, CanalNotificacao,
)


class Base(DeclarativeBase):
    """Classe base declarativa para todos os modelos ORM."""
    pass


# --------------------------------------------------------------------------
# USUÁRIOS
# --------------------------------------------------------------------------
class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome_completo: Mapped[str] = mapped_column(String(150), nullable=False)
    login: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nivel_acesso: Mapped[NivelAcesso] = mapped_column(
        SAEnum(NivelAcesso, name="nivel_acesso_enum"), nullable=False, default=NivelAcesso.OPERADOR
    )
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tentativas_login_falhas: Mapped[int] = mapped_column(Integer, default=0)
    bloqueado_ate: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    criado_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ultimo_login: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    logs: Mapped[List["Log"]] = relationship(back_populates="usuario")
    alertas_reconhecidos: Mapped[List["Alerta"]] = relationship(back_populates="reconhecido_por")

    def __repr__(self) -> str:
        return f"<Usuario {self.login} ({self.nivel_acesso})>"


# --------------------------------------------------------------------------
# CÂMERAS
# --------------------------------------------------------------------------
class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    localizacao: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    protocolo: Mapped[ProtocoloCamera] = mapped_column(
        SAEnum(ProtocoloCamera, name="protocolo_camera_enum"), default=ProtocoloCamera.RTSP
    )
    url_rtsp: Mapped[str] = mapped_column(String(500), nullable=False)
    # Dados de acesso ONVIF (opcional, usado para PTZ/descoberta/telemetria)
    onvif_host: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    onvif_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=80)
    onvif_usuario: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    onvif_senha: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    ativa: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[StatusCamera] = mapped_column(
        SAEnum(StatusCamera, name="status_camera_enum"), default=StatusCamera.OFFLINE
    )
    fps_alvo: Mapped[int] = mapped_column(Integer, default=10)
    zona_deteccao_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # polígono ROI opcional

    criado_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    epis_obrigatorios: Mapped[List["CameraEPI"]] = relationship(
        back_populates="camera", cascade="all, delete-orphan"
    )
    eventos: Mapped[List["Evento"]] = relationship(back_populates="camera")

    def __repr__(self) -> str:
        return f"<Camera {self.nome} [{self.status}]>"


class CameraEPI(Base):
    """Associação N:N entre Câmera e os EPIs obrigatórios naquele ponto."""
    __tablename__ = "camera_epis"
    __table_args__ = (UniqueConstraint("camera_id", "tipo_epi", name="uq_camera_epi"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False)
    tipo_epi: Mapped[TipoEPI] = mapped_column(SAEnum(TipoEPI, name="tipo_epi_enum"), nullable=False)
    obrigatorio: Mapped[bool] = mapped_column(Boolean, default=True)

    camera: Mapped["Camera"] = relationship(back_populates="epis_obrigatorios")


# --------------------------------------------------------------------------
# EVENTOS
# --------------------------------------------------------------------------
class Evento(Base):
    """
    Um evento é qualquer ocorrência detectada pelo sistema: uma infração,
    uma conformidade, ou um evento de sistema (câmera caiu, etc.).
    """
    __tablename__ = "eventos"
    __table_args__ = (
        Index("idx_evento_data_tipo", "data_hora", "tipo_evento"),
        Index("idx_evento_camera_tipo_data", "camera_id", "tipo_evento", "data_hora"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True)
    tipo_evento: Mapped[TipoEvento] = mapped_column(SAEnum(TipoEvento, name="tipo_evento_enum"), nullable=False)

    epis_ausentes_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # lista JSON de TipoEPI
    confianca_media: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    caminho_snapshot: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    caminho_video_clip: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    data_hora: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    observacoes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    camera: Mapped[Optional["Camera"]] = relationship(back_populates="eventos")
    alertas: Mapped[List["Alerta"]] = relationship(back_populates="evento", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Evento {self.tipo_evento} cam={self.camera_id} em {self.data_hora}>"


# --------------------------------------------------------------------------
# ALERTAS
# --------------------------------------------------------------------------
class Alerta(Base):
    __tablename__ = "alertas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id", ondelete="CASCADE"), nullable=False)

    severidade: Mapped[SeveridadeAlerta] = mapped_column(
        SAEnum(SeveridadeAlerta, name="severidade_alerta_enum"), default=SeveridadeAlerta.MEDIA
    )
    status: Mapped[StatusAlerta] = mapped_column(
        SAEnum(StatusAlerta, name="status_alerta_enum"), default=StatusAlerta.PENDENTE
    )
    canal: Mapped[CanalNotificacao] = mapped_column(
        SAEnum(CanalNotificacao, name="canal_notificacao_enum"), default=CanalNotificacao.SISTEMA
    )
    mensagem: Mapped[str] = mapped_column(Text, nullable=False)

    criado_em: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reconhecido_em: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reconhecido_por_id: Mapped[Optional[int]] = mapped_column(ForeignKey("usuarios.id"), nullable=True)

    evento: Mapped["Evento"] = relationship(back_populates="alertas")
    reconhecido_por: Mapped[Optional["Usuario"]] = relationship(back_populates="alertas_reconhecidos")

    def __repr__(self) -> str:
        return f"<Alerta #{self.id} [{self.status}] sev={self.severidade}>"


# --------------------------------------------------------------------------
# CONFIGURAÇÕES (chave/valor, editável pela UI em tempo de execução)
# --------------------------------------------------------------------------
class Configuracao(Base):
    __tablename__ = "configuracoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chave: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    valor: Mapped[str] = mapped_column(Text, nullable=False)
    descricao: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    atualizado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# --------------------------------------------------------------------------
# LOGS (auditoria do sistema: login, alterações, erros)
# --------------------------------------------------------------------------
class NivelLog(str, enum.Enum):
    INFO = "info"
    AVISO = "aviso"
    ERRO = "erro"
    CRITICO = "critico"


class Log(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usuario_id: Mapped[Optional[int]] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    nivel: Mapped[NivelLog] = mapped_column(SAEnum(NivelLog, name="nivel_log_enum"), default=NivelLog.INFO)
    origem: Mapped[str] = mapped_column(String(100), nullable=False)  # ex: "auth", "camera_service", "detection"
    mensagem: Mapped[str] = mapped_column(Text, nullable=False)
    data_hora: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    usuario: Mapped[Optional["Usuario"]] = relationship(back_populates="logs")
