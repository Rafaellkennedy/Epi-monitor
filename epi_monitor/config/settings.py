"""
config/settings.py
-------------------
Configurações globais do sistema EPI Monitor.

Este módulo centraliza TODAS as configurações da aplicação, seguindo o
princípio de "single source of truth". Nada de valores mágicos espalhados
pelo código: tudo que é configurável vive aqui ou no banco de dados
(tabela `configuracoes`, para parâmetros que o usuário pode alterar
em tempo de execução pela UI).

As variáveis sensíveis (senha do banco, SMTP, etc.) são lidas de um
arquivo `.env` na raiz do projeto (nunca comitar esse arquivo).
"""

from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env, se existir
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _get_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _get_int(key: str, default: int) -> int:
    val = os.getenv(key)
    try:
        return int(val) if val is not None else default
    except ValueError:
        return default


@dataclass(frozen=True)
class DatabaseSettings:
    """Parâmetros de conexão com o PostgreSQL."""
    host: str = os.getenv("DB_HOST", "localhost")
    port: int = _get_int("DB_PORT", 5432)
    name: str = os.getenv("DB_NAME", "epi_monitor")
    user: str = os.getenv("DB_USER", "postgres")
    password: str = os.getenv("DB_PASSWORD", "postgres")

    @property
    def url(self) -> str:
        """URL de conexão SQLAlchemy (driver psycopg2)."""
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )


@dataclass(frozen=True)
class DetectionSettings:
    """Parâmetros do motor de detecção YOLO."""
    # Caminho do modelo treinado (best.pt). Pode ser um modelo customizado
    # treinado especificamente para EPIs (recomendado) ou o modelo base.
    model_path: str = os.getenv("YOLO_MODEL_PATH", str(BASE_DIR / "resources" / "models" / "epi_best.pt"))

    # Confiança mínima para considerar uma detecção válida (0.0 a 1.0)
    confidence_threshold: float = float(os.getenv("YOLO_CONFIDENCE", "0.5"))

    # IoU threshold usado no NMS (Non-Max Suppression)
    iou_threshold: float = float(os.getenv("YOLO_IOU", "0.45"))

    # Dispositivo de inferência: "cuda:0" (GPU NVIDIA), "cpu" ou "auto"
    device: str = os.getenv("YOLO_DEVICE", "auto")

    # Tamanho da imagem de entrada para o modelo (múltiplo de 32)
    img_size: int = _get_int("YOLO_IMG_SIZE", 640)

    # A cada quantos frames processar a inferência (para aliviar CPU/GPU
    # em cenários com muitas câmeras). 1 = processa todos os frames.
    frame_skip: int = _get_int("YOLO_FRAME_SKIP", 3)

    # Classes que o modelo deve reconhecer (mapeamento id -> nome).
    # Ajustar conforme o dataset usado no treinamento do modelo customizado.
    class_names: dict = field(default_factory=lambda: {
        0: "capacete",
        1: "sem_capacete",
        2: "oculos",
        3: "sem_oculos",
        4: "colete",
        5: "sem_colete",
        6: "mascara",
        7: "sem_mascara",
        8: "luvas",
        9: "sem_luvas",
        10: "pessoa",
    })

    # Mapa de equivalência: nome nativo do modelo de terceiros -> nome interno EPI.
    # Ex.: modelo "Construction Site Safety" do Roboflow tem as classes abaixo.
    # Classes nativas não listadas aqui mas no `discard_classes` serão descartadas.
    epi_equivalence_map: dict = field(default_factory=lambda: {
        "Hardhat": "capacete",
        "NO-Hardhat": "sem_capacete",
        "Mask": "mascara",
        "NO-Mask": "sem_mascara",
        "Safety Vest": "colete",
        "NO-Safety Vest": "sem_colete",
        "Person": "pessoa",
    })

    # Classes de modelos de terceiros que devem ser descartadas (não são EPIs/pessoas).
    epi_discard_classes: set = field(default_factory=lambda: {
        "Safety Cone", "machinery", "vehicle",
    })


@dataclass(frozen=True)
class CameraSettings:
    """Parâmetros gerais de conexão e captura de câmeras."""
    max_cameras: int = _get_int("MAX_CAMERAS", 50)
    reconnect_interval_sec: int = _get_int("CAMERA_RECONNECT_INTERVAL", 5)
    connection_timeout_sec: int = _get_int("CAMERA_CONNECTION_TIMEOUT", 10)
    # Buffer de frames para reduzir uso de memória / latência
    frame_queue_size: int = _get_int("CAMERA_FRAME_QUEUE_SIZE", 2)
    # FPS alvo de processamento (independente do FPS nativo da câmera)
    target_fps: int = _get_int("CAMERA_TARGET_FPS", 10)


@dataclass(frozen=True)
class AlertSettings:
    """Configurações de alertas (sonoro, e-mail, etc.)."""
    sound_enabled: bool = _get_bool("ALERT_SOUND_ENABLED", True)
    sound_file: str = os.getenv("ALERT_SOUND_FILE", str(BASE_DIR / "resources" / "sounds" / "alarme.wav"))

    # Tempo mínimo (segundos) entre alertas repetidos da MESMA câmera,
    # para evitar spam de notificações na mesma infração contínua.
    cooldown_sec: int = _get_int("ALERT_COOLDOWN_SEC", 30)

    # SMTP para envio de e-mail
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = _get_int("SMTP_PORT", 587)
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_use_tls: bool = _get_bool("SMTP_USE_TLS", True)
    email_enabled: bool = _get_bool("EMAIL_ALERTS_ENABLED", False)

    # Placeholders para integrações futuras (documentadas no README)
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    whatsapp_api_url: str = os.getenv("WHATSAPP_API_URL", "")
    whatsapp_api_token: str = os.getenv("WHATSAPP_API_TOKEN", "")


@dataclass(frozen=True)
class StorageSettings:
    """Locais de armazenamento de evidências (fotos/vídeos)."""
    base_dir: Path = BASE_DIR / "storage"
    snapshots_dir: Path = BASE_DIR / "storage" / "snapshots"
    clips_dir: Path = BASE_DIR / "storage" / "clips"
    logs_dir: Path = BASE_DIR / "storage" / "logs"

    # Duração do clipe de vídeo gravado na ocorrência (segundos)
    clip_duration_sec: int = _get_int("CLIP_DURATION_SEC", 10)

    # Retenção de evidências em dias (rotina de limpeza automática)
    retention_days: int = _get_int("STORAGE_RETENTION_DAYS", 90)

    def ensure_dirs(self) -> None:
        for d in (self.base_dir, self.snapshots_dir, self.clips_dir, self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class UISettings:
    """Configurações da interface gráfica."""
    app_name: str = "EPI Monitor - Sistema de Monitoramento de EPIs"
    org_name: str = "EPI Monitor"
    default_theme: str = os.getenv("UI_THEME", "dark")  # "dark" ou "light"
    grid_columns_default: int = _get_int("UI_GRID_COLUMNS", 3)
    window_min_width: int = 1280
    window_min_height: int = 800


@dataclass(frozen=True)
class SecuritySettings:
    """Configurações de segurança/autenticação."""
    # Chave secreta usada para assinar tokens de sessão internos.
    # Em produção, definir via variável de ambiente SECRET_KEY.
    secret_key: str = os.getenv("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION_ENV_FILE")
    session_timeout_min: int = _get_int("SESSION_TIMEOUT_MIN", 480)
    max_login_attempts: int = _get_int("MAX_LOGIN_ATTEMPTS", 5)
    lockout_minutes: int = _get_int("LOCKOUT_MINUTES", 15)


@dataclass(frozen=True)
class Settings:
    """Agregador de todas as configurações da aplicação."""
    database: DatabaseSettings = field(default_factory=DatabaseSettings)
    detection: DetectionSettings = field(default_factory=DetectionSettings)
    camera: CameraSettings = field(default_factory=CameraSettings)
    alert: AlertSettings = field(default_factory=AlertSettings)
    storage: StorageSettings = field(default_factory=StorageSettings)
    ui: UISettings = field(default_factory=UISettings)
    security: SecuritySettings = field(default_factory=SecuritySettings)

    debug: bool = _get_bool("DEBUG", False)


# Instância única (singleton) usada em todo o projeto:
# from config.settings import settings
settings = Settings()
settings.storage.ensure_dirs()
