"""
services/camera_service.py
----------------------------
Implementa a captura de vídeo de UMA câmera em uma thread dedicada.

Cada câmera do sistema roda em sua própria `CameraStream`, que:
    1. Conecta via OpenCV (backend FFmpeg) na URL RTSP.
    2. Captura frames continuamente, mantendo sempre o frame MAIS RECENTE
       disponível (descarta frames antigos para não acumular latência).
    3. Reconecta automaticamente em caso de queda de sinal.
    4. Expõe o último frame de forma thread-safe para o pipeline de detecção.

Com até 50 câmeras simultâneas, usar 50 threads Python é aceitável pois o
gargalo real é I/O de rede (GIL libera durante leitura do socket/FFmpeg).
A INFERÊNCIA (uso pesado de CPU/GPU) é feita em um pool separado
(ver services/detection_pipeline.py) para não competir com a captura.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional, Callable

import cv2
import numpy as np

from config.settings import settings
from models.enums import StatusCamera

logger = logging.getLogger(__name__)


@dataclass
class CameraConfig:
    """Configuração mínima necessária para abrir uma câmera."""
    id: int
    nome: str
    url_rtsp: str
    fps_alvo: int = 10


class CameraStream:
    """
    Gerencia a conexão e captura contínua de uma única câmera em thread própria.

    Uso:
        stream = CameraStream(config, on_status_change=callback)
        stream.start()
        frame = stream.get_latest_frame()   # thread-safe, não bloqueante
        stream.stop()
    """

    def __init__(
        self,
        config: CameraConfig,
        on_status_change: Optional[Callable[[int, StatusCamera], None]] = None,
    ) -> None:
        self.config = config
        self.on_status_change = on_status_change

        self._cap: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_frame_ts: float = 0.0
        self.status = StatusCamera.OFFLINE

        # Buffer circular pequeno usado pela gravação de clipes (pré-evento).
        # Mantém os últimos N segundos em memória para poder gravar também
        # o instante ANTES do disparo do alerta.
        self._pre_buffer_seconds = 5
        self._pre_buffer_max_frames = max(self.config.fps_alvo, 1) * self._pre_buffer_seconds
        self._pre_buffer: deque[tuple[float, bytes]] = deque(maxlen=self._pre_buffer_max_frames)

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._running.set()
        self._thread = threading.Thread(target=self._loop_captura, name=f"cam-{self.config.id}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=3)
        if self._cap:
            self._cap.release()
        self._set_status(StatusCamera.DESATIVADA)

    # ------------------------------------------------------------------
    # Loop principal (roda em thread separada)
    # ------------------------------------------------------------------
    def _loop_captura(self) -> None:
        intervalo_frame = 1.0 / max(self.config.fps_alvo, 1)

        while self._running.is_set():
            if not self._conectar():
                self._set_status(StatusCamera.RECONECTANDO)
                time.sleep(settings.camera.reconnect_interval_sec)
                continue

            self._set_status(StatusCamera.ONLINE)

            while self._running.is_set():
                t0 = time.time()
                ok, frame = self._cap.read()

                if not ok or frame is None:
                    logger.warning(f"[{self.config.nome}] Falha na leitura do frame. Reconectando...")
                    self._set_status(StatusCamera.RECONECTANDO)
                    break  # sai do loop interno -> tenta reconectar no loop externo

                with self._lock:
                    self._latest_frame = frame
                    self._latest_frame_ts = time.time()
                    self._atualizar_pre_buffer(frame)

                # Regula o FPS de captura para não sobrecarregar a CPU
                elapsed = time.time() - t0
                sleep_time = intervalo_frame - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

            if self._cap:
                self._cap.release()
                self._cap = None

        self._set_status(StatusCamera.DESATIVADA)

    def _conectar(self) -> bool:
        try:
            # CAP_FFMPEG garante uso do backend FFmpeg (necessário para RTSP)
            self._cap = cv2.VideoCapture(self.config.url_rtsp, cv2.CAP_FFMPEG)
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # minimiza latência

            if not self._cap.isOpened():
                logger.error(f"[{self.config.nome}] Não foi possível abrir o stream: {self.config.url_rtsp}")
                self._set_status(StatusCamera.ERRO)
                return False

            logger.info(f"[{self.config.nome}] Conectado com sucesso.")
            return True
        except Exception as e:
            logger.error(f"[{self.config.nome}] Erro ao conectar: {e}")
            self._set_status(StatusCamera.ERRO)
            return False

    # ------------------------------------------------------------------
    # Acesso thread-safe ao frame mais recente
    # ------------------------------------------------------------------
    def get_latest_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return None if self._latest_frame is None else self._latest_frame.copy()

    def get_pre_buffer(self) -> list[np.ndarray]:
        """Retorna cópia decodificada dos frames dos últimos segundos (para gravação de clipe)."""
        with self._lock:
            copia_buffer = list(self._pre_buffer)

        frames_decodificados: list[np.ndarray] = []
        for _, jpg_bytes in copia_buffer:
            nparr = np.frombuffer(jpg_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is not None:
                frames_decodificados.append(img)
        return frames_decodificados

    def _atualizar_pre_buffer(self, frame: np.ndarray) -> None:
        agora = time.time()
        ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ok:
            self._pre_buffer.append((agora, buffer.tobytes()))

    def _set_status(self, status: StatusCamera) -> None:
        if status != self.status:
            self.status = status
            if self.on_status_change:
                self.on_status_change(self.config.id, status)


class CameraManager:
    """
    Orquestra múltiplas `CameraStream` simultaneamente (até 50, conforme
    especificação). Ponto único de acesso para o restante da aplicação
    iniciar/parar/consultar câmeras.
    """

    def __init__(self) -> None:
        self._streams: dict[int, CameraStream] = {}

    def adicionar_camera(self, config: CameraConfig, on_status_change=None) -> CameraStream:
        if len(self._streams) >= settings.camera.max_cameras:
            raise RuntimeError(f"Limite máximo de {settings.camera.max_cameras} câmeras atingido.")

        stream = CameraStream(config, on_status_change=on_status_change)
        self._streams[config.id] = stream
        stream.start()
        return stream

    def remover_camera(self, camera_id: int) -> None:
        stream = self._streams.pop(camera_id, None)
        if stream:
            stream.stop()

    def get_stream(self, camera_id: int) -> Optional[CameraStream]:
        return self._streams.get(camera_id)

    def get_all_streams(self) -> dict[int, CameraStream]:
        return dict(self._streams)

    def parar_todas(self) -> None:
        for stream in self._streams.values():
            stream.stop()
        self._streams.clear()
