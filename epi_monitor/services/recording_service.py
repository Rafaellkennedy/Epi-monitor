"""
services/recording_service.py
--------------------------------
Responsável por persistir as EVIDÊNCIAS de uma infração em disco:
    1. Snapshot (imagem JPEG) do frame exato da detecção.
    2. Clipe de vídeo curto (padrão 10s) contendo alguns segundos ANTES
       e DEPOIS do momento da infração, usando o pré-buffer mantido pela
       `CameraStream` (services/camera_service.py) mais frames capturados
       em tempo real após o disparo.

O nome dos arquivos segue o padrão:
    {camera_id}_{AAAAMMDD_HHMMSS}.jpg / .mp4
o que facilita auditoria e limpeza automática por data.
"""

from __future__ import annotations

import datetime
import logging
import threading
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

from config.settings import settings
from services.camera_service import CameraStream

logger = logging.getLogger(__name__)


class RecordingService:
    """Salva snapshots e clipes de vídeo das infrações detectadas."""

    def __init__(self) -> None:
        self.snapshots_dir = settings.storage.snapshots_dir
        self.clips_dir = settings.storage.clips_dir
        self.clip_duration = settings.storage.clip_duration_sec

    # ------------------------------------------------------------------
    def salvar_snapshot(self, camera_id: int, frame: np.ndarray) -> str:
        """Salva a imagem do frame da infração e retorna o caminho salvo."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        nome_arquivo = f"cam{camera_id}_{timestamp}.jpg"
        caminho = self.snapshots_dir / nome_arquivo
        cv2.imwrite(str(caminho), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        logger.info(f"Snapshot salvo: {caminho}")
        return str(caminho)

    # ------------------------------------------------------------------
    def gravar_clipe_async(self, camera_id: int, stream: CameraStream, fps: int = 10) -> None:
        """
        Dispara a gravação do clipe de vídeo em uma thread separada, para
        não bloquear o pipeline de detecção enquanto captura os frames
        "pós-evento" (alguns segundos após o disparo do alerta).
        """
        t = threading.Thread(
            target=self._gravar_clipe,
            args=(camera_id, stream, fps),
            daemon=True,
            name=f"clip-recorder-cam-{camera_id}",
        )
        t.start()

    def _gravar_clipe(self, camera_id: int, stream: CameraStream, fps: int) -> Optional[str]:
        import time

        # 1) Frames PRÉ-evento (já capturados pelo buffer circular da câmera)
        frames_pre: List[np.ndarray] = stream.get_pre_buffer()

        # 2) Frames PÓS-evento: aguarda e coleta em tempo real
        metade_pos_segundos = max(self.clip_duration - len(frames_pre) / max(fps, 1), self.clip_duration / 2)
        frames_pos: List[np.ndarray] = []
        intervalo = 1.0 / max(fps, 1)
        inicio = time.time()
        while time.time() - inicio < metade_pos_segundos:
            frame = stream.get_latest_frame()
            if frame is not None:
                frames_pos.append(frame)
            time.sleep(intervalo)

        frames_totais = frames_pre + frames_pos
        if not frames_totais:
            logger.warning(f"[cam {camera_id}] Nenhum frame disponível para gravar clipe.")
            return None

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"cam{camera_id}_{timestamp}.mp4"
        caminho = self.clips_dir / nome_arquivo

        altura, largura = frames_totais[0].shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(caminho), fourcc, fps, (largura, altura))

        try:
            for f in frames_totais:
                if f.shape[:2] != (altura, largura):
                    f = cv2.resize(f, (largura, altura))
                writer.write(f)
        finally:
            writer.release()

        logger.info(f"Clipe de vídeo salvo: {caminho} ({len(frames_totais)} frames)")
        return str(caminho)

    # ------------------------------------------------------------------
    def limpar_evidencias_antigas(self) -> int:
        """
        Rotina de manutenção: remove snapshots/clipes mais antigos que o
        período de retenção configurado (settings.storage.retention_days).
        Deve ser chamada periodicamente (ex.: agendador diário).
        """
        limite = datetime.datetime.now() - datetime.timedelta(days=settings.storage.retention_days)
        removidos = 0
        for pasta in (self.snapshots_dir, self.clips_dir):
            for arquivo in Path(pasta).glob("*"):
                if arquivo.is_file():
                    mtime = datetime.datetime.fromtimestamp(arquivo.stat().st_mtime)
                    if mtime < limite:
                        arquivo.unlink(missing_ok=True)
                        removidos += 1
        logger.info(f"Limpeza de evidências: {removidos} arquivo(s) removido(s).")
        return removidos
