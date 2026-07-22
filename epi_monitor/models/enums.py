"""
models/enums.py
----------------
Enumeradores de domínio, usados tanto pelas entidades do banco de dados
quanto pela camada de serviços/UI. Centralizar aqui evita "strings mágicas"
espalhadas pelo código (ex.: comparar cargo == "admin" em 10 lugares diferentes).
"""

import enum


class NivelAcesso(str, enum.Enum):
    """Níveis de acesso de um usuário no sistema."""
    ADMINISTRADOR = "administrador"
    TECNICO_SEGURANCA = "tecnico_seguranca"
    OPERADOR = "operador"


class ProtocoloCamera(str, enum.Enum):
    """Protocolo de conexão utilizado pela câmera."""
    RTSP = "rtsp"
    ONVIF = "onvif"
    HTTP = "http"


class StatusCamera(str, enum.Enum):
    """Status de conexão atual da câmera."""
    ONLINE = "online"
    OFFLINE = "offline"
    RECONECTANDO = "reconectando"
    ERRO = "erro"
    DESATIVADA = "desativada"


class TipoEPI(str, enum.Enum):
    """Tipos de Equipamento de Proteção Individual monitorados."""
    CAPACETE = "capacete"
    OCULOS = "oculos"
    COLETE = "colete"
    MASCARA = "mascara"
    LUVAS = "luvas"


class TipoEvento(str, enum.Enum):
    """Tipos de evento registrados pelo sistema."""
    CONFORMIDADE = "conformidade"      # funcionário com todos os EPIs
    INFRACAO = "infracao"              # funcionário sem 1+ EPI obrigatório
    CAMERA_OFFLINE = "camera_offline"
    CAMERA_ONLINE = "camera_online"
    SISTEMA = "sistema"


class SeveridadeAlerta(str, enum.Enum):
    """Severidade de um alerta gerado."""
    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"


class StatusAlerta(str, enum.Enum):
    """Ciclo de vida de um alerta."""
    PENDENTE = "pendente"
    NOTIFICADO = "notificado"
    RECONHECIDO = "reconhecido"       # técnico deu ciência
    RESOLVIDO = "resolvido"
    FALSO_POSITIVO = "falso_positivo"


class CanalNotificacao(str, enum.Enum):
    """Canais de envio de notificação de alerta."""
    SISTEMA = "sistema"     # notificação interna na UI
    EMAIL = "email"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    SOM = "som"
