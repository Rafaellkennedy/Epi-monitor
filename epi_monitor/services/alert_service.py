"""
services/alert_service.py
----------------------------
Dispara e gerencia alertas quando uma infração é detectada:
    - Toca alarme sonoro localmente.
    - Envia notificação interna para a UI (via callback/signal).
    - Persiste o alerta no banco (tabela `alertas`).
    - Envia e-mail (se habilitado).
    - Pontos de extensão prontos para Telegram e WhatsApp (documentado
      no README, requer apenas implementar os métodos marcados TODO).

Cooldown: para não gerar um alerta a cada frame durante uma infração
contínua (ex.: pessoa parada sem capacete por 2 minutos), mantemos um
registro em memória do último alerta de cada câmera e só disparamos um
novo após `settings.alert.cooldown_sec`.
"""

from __future__ import annotations

import logging
import smtplib
import threading
import time
import json
import urllib.request
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from pathlib import Path
from typing import Callable, Optional

from config.settings import settings
from database.connection import get_session
from database.models import Alerta, Evento
from models.enums import SeveridadeAlerta, StatusAlerta, CanalNotificacao, TipoEPI

logger = logging.getLogger(__name__)

# Callback opcional para tocar som (injetado pela camada de UI, que sabe
# como reproduzir áudio no toolkit Qt sem acoplar este serviço à UI).
SoundPlayer = Callable[[str], None]
NotificationCallback = Callable[[dict], None]


class AlertService:
    def __init__(self, sound_player: Optional[SoundPlayer] = None,
                 notification_callback: Optional[NotificationCallback] = None) -> None:
        self.sound_player = sound_player
        self.notification_callback = notification_callback
        self._ultimo_alerta_por_camera: dict[int, float] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def pode_disparar(self, camera_id: int) -> bool:
        """Verifica se o cooldown já expirou para esta câmera."""
        with self._lock:
            ultimo = self._ultimo_alerta_por_camera.get(camera_id, 0.0)
            return (time.time() - ultimo) >= settings.alert.cooldown_sec

    def _marcar_disparo(self, camera_id: int) -> None:
        with self._lock:
            self._ultimo_alerta_por_camera[camera_id] = time.time()

    # ------------------------------------------------------------------
    def disparar_alerta(
        self,
        evento: Evento,
        camera_nome: str,
        epis_ausentes: list[TipoEPI],
        snapshot_path: Optional[str] = None,
    ) -> Optional[Alerta]:
        """
        Ponto de entrada principal: cria o alerta no banco e dispara os
        canais de notificação configurados (som, sistema, e-mail...).
        """
        if not self.pode_disparar(evento.camera_id):
            return None  # ainda em cooldown, ignora para evitar spam

        self._marcar_disparo(evento.camera_id)

        severidade = self._calcular_severidade(epis_ausentes)
        mensagem = (
            f"Infração detectada na câmera '{camera_nome}': "
            f"ausência de {', '.join(e.value for e in epis_ausentes)}."
        )

        with get_session() as session:
            alerta = Alerta(
                evento_id=evento.id,
                severidade=severidade,
                status=StatusAlerta.NOTIFICADO,
                canal=CanalNotificacao.SISTEMA,
                mensagem=mensagem,
            )
            session.add(alerta)
            session.commit()
            session.refresh(alerta)
            session.expunge(alerta)

        # Dispara canais (cada um trata sua própria exceção para não
        # derrubar o pipeline de detecção por causa de um SMTP fora do ar)
        self._tocar_som()
        self._notificar_sistema(alerta, camera_nome, mensagem)
        if settings.alert.email_enabled:
            self._enviar_email_async(camera_nome, mensagem, snapshot_path)
            
        if settings.alert.telegram_bot_token and settings.alert.telegram_chat_id:
            self.enviar_telegram_async(mensagem, snapshot_path)
            
        if settings.alert.whatsapp_api_url and settings.alert.whatsapp_api_token:
            self.enviar_whatsapp_async(mensagem, snapshot_path)

        return alerta

    # ------------------------------------------------------------------
    @staticmethod
    def _calcular_severidade(epis_ausentes: list[TipoEPI]) -> SeveridadeAlerta:
        """Define severidade com base na quantidade/tipo de EPI ausente.
        Capacete e óculos ausentes em áreas de risco são tratados como mais críticos."""
        criticos = {TipoEPI.CAPACETE, TipoEPI.OCULOS}
        if any(e in criticos for e in epis_ausentes) and len(epis_ausentes) >= 2:
            return SeveridadeAlerta.CRITICA
        if any(e in criticos for e in epis_ausentes):
            return SeveridadeAlerta.ALTA
        if len(epis_ausentes) >= 2:
            return SeveridadeAlerta.MEDIA
        return SeveridadeAlerta.BAIXA

    def _tocar_som(self) -> None:
        if not settings.alert.sound_enabled:
            return
        if self.sound_player:
            try:
                self.sound_player(settings.alert.sound_file)
            except Exception as e:
                logger.error(f"Erro ao tocar som de alerta: {e}")

    def _notificar_sistema(self, alerta: Alerta, camera_nome: str, mensagem: str) -> None:
        if self.notification_callback:
            try:
                self.notification_callback({
                    "alerta_id": alerta.id,
                    "camera": camera_nome,
                    "mensagem": mensagem,
                    "severidade": alerta.severidade.value,
                })
            except Exception as e:
                logger.error(f"Erro ao notificar UI: {e}")

    # ------------------------------------------------------------------
    def _enviar_email_async(self, camera_nome: str, mensagem: str, snapshot_path: Optional[str]) -> None:
        t = threading.Thread(target=self._enviar_email, args=(camera_nome, mensagem, snapshot_path), daemon=True)
        t.start()

    def _enviar_email(self, camera_nome: str, mensagem: str, snapshot_path: Optional[str]) -> None:
        try:
            msg = MIMEMultipart()
            msg["Subject"] = f"[EPI Monitor] Infração detectada - {camera_nome}"
            msg["From"] = settings.alert.smtp_user
            msg["To"] = settings.alert.smtp_user  # TODO: destinatários configuráveis via tela de Configurações
            msg.attach(MIMEText(mensagem, "plain", "utf-8"))

            if snapshot_path and Path(snapshot_path).exists():
                with open(snapshot_path, "rb") as f:
                    img = MIMEImage(f.read())
                    img.add_header("Content-Disposition", "attachment", filename=Path(snapshot_path).name)
                    msg.attach(img)

            with smtplib.SMTP(settings.alert.smtp_host, settings.alert.smtp_port, timeout=10) as server:
                if settings.alert.smtp_use_tls:
                    server.starttls()
                server.login(settings.alert.smtp_user, settings.alert.smtp_password)
                server.send_message(msg)

            logger.info(f"E-mail de alerta enviado para câmera '{camera_nome}'.")
        except Exception as e:
            logger.error(f"Falha ao enviar e-mail de alerta: {e}")

    # ------------------------------------------------------------------
    # Pontos de extensão para integrações futuras (não implementadas,
    # mas com assinatura pronta e documentada para facilitar o próximo dev).
    # ------------------------------------------------------------------
    def enviar_telegram_async(self, mensagem: str, snapshot_path: str | None = None) -> None:
        t = threading.Thread(target=self.enviar_telegram, args=(mensagem, snapshot_path), daemon=True)
        t.start()

    def enviar_telegram(self, mensagem: str, snapshot_path: str | None = None) -> None:
        token = settings.alert.telegram_bot_token
        chat_id = settings.alert.telegram_chat_id

        if not token or not chat_id:
            logger.warning("Telegram Bot Token ou Chat ID não configurados.")
            return

        try:
            if snapshot_path and Path(snapshot_path).exists():
                url = f"https://api.telegram.org/bot{token}/sendPhoto"
                # Monta multipart/form-data via urllib para upload da imagem JPEG
                boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
                data = []
                data.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{chat_id}\r\n".encode())
                data.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{mensagem}\r\n".encode())
                
                with open(snapshot_path, "rb") as f:
                    filename = Path(snapshot_path).name
                    data.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"{filename}\"\r\nContent-Type: image/jpeg\r\n\r\n".encode())
                    data.append(f.read())
                    data.append(b"\r\n")
                
                data.append(f"--{boundary}--\r\n".encode())
                body = b"".join(data)

                req = urllib.request.Request(url, data=body)
                req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    logger.info(f"Notificação Telegram enviada com sucesso: {resp.status}")
            else:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                payload = json.dumps({"chat_id": chat_id, "text": mensagem}).encode('utf-8')
                req = urllib.request.Request(url, data=payload, method="POST")
                req.add_header("Content-Type", "application/json")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    logger.info(f"Notificação Telegram (apenas texto) enviada com sucesso: {resp.status}")

        except Exception as e:
            logger.error(f"Falha ao enviar mensagem via Telegram: {e}")

    def enviar_whatsapp_async(self, mensagem: str, snapshot_path: str | None = None) -> None:
        t = threading.Thread(target=self.enviar_whatsapp, args=(mensagem, snapshot_path), daemon=True)
        t.start()

    def enviar_whatsapp(self, mensagem: str, snapshot_path: str | None = None) -> None:
        url = settings.alert.whatsapp_api_url
        token = settings.alert.whatsapp_api_token
        
        if not url or not token:
            logger.warning("WhatsApp API URL ou Token não configurados.")
            return
            
        try:
            payload_dict = {
                "message": mensagem
            }
            # Em uma implementação real, trataríamos o anexo em base64 se a API suportar
            payload = json.dumps(payload_dict).encode('utf-8')
            req = urllib.request.Request(url, data=payload, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("Authorization", f"Bearer {token}")
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info(f"Notificação WhatsApp enviada com sucesso: {resp.status}")
        except Exception as e:
            logger.error(f"Falha ao enviar mensagem via WhatsApp: {e}")
