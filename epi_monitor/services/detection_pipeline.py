"""
services/detection_pipeline.py
---------------------------------
Este é o "maestro" do sistema: orquestra, para CADA câmera ativa, o ciclo:

    captura (CameraStream) -> inferência (YoloDetector) -> checagem (EPIChecker)
        -> emite frame anotado para a UI -> se infração: salva evidências,
           registra evento, dispara alerta.

Desempenho com até 50 câmeras:
    - A CAPTURA de cada câmera roda em sua própria thread leve (I/O bound),
      já gerenciada pelo CameraManager.
    - A INFERÊNCIA (CPU/GPU bound) roda em um ThreadPoolExecutor com um
      número limitado de workers (configurável), para não sobrecarregar
      a GPU/CPU tentando rodar 50 inferências ao mesmo tempo. O Ultralytics
      processa cada `predict()` de forma otimizada; o pool controla a
      CONCORRÊNCIA, não o paralelismo real da GPU (que processa em lote
      internamente via CUDA streams).
    - `frame_skip` (config) permite pular frames e analisar, por exemplo,
      1 a cada 3 capturados — ajustável conforme hardware disponível.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Callable, Optional

from config.settings import settings
from database.models import Camera
from detection.yolo_detector import YoloDetector
from detection.epi_checker import EPIChecker
from models.detection import ResultadoAnalise
from services.camera_service import CameraManager, CameraConfig
from services.camera_repository import CameraRepository
from services.event_service import EventService
from services.alert_service import AlertService
from services.recording_service import RecordingService
from models.enums import StatusCamera, TipoEvento

logger = logging.getLogger(__name__)

# Callback que a UI registra para receber cada frame processado
FrameCallback = Callable[[int, ResultadoAnalise], None]


class DetectionPipeline:
    """
    Ponto único de coordenação do sistema de monitoramento em tempo real.
    A UI interage apenas com esta classe (start/stop/registrar callback),
    sem precisar conhecer os detalhes internos de captura/inferência.
    """

    def __init__(
        self,
        camera_manager: CameraManager,
        alert_service: AlertService,
        batch_size: int = 4,
        timeout_ms: float = 0.015,
    ) -> None:
        self.camera_manager = camera_manager
        self.alert_service = alert_service
        self.recording_service = RecordingService()
        self.detector = YoloDetector.get_instance()
        self.batch_size = batch_size
        self.timeout_sec = timeout_ms

        self._frame_queue: queue.Queue = queue.Queue(maxsize=100)
        self._checkers: dict[int, EPIChecker] = {}
        self._frame_callback: Optional[FrameCallback] = None
        self._contador_frames: dict[int, int] = {}
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._batch_worker_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    def registrar_callback_frame(self, callback: FrameCallback) -> None:
        """A UI chama isto para receber cada `ResultadoAnalise` processado."""
        self._frame_callback = callback

    def iniciar_camera(self, camera: Camera) -> None:
        """Inicia captura + análise para uma câmera cadastrada."""
        epis_obrigatorios = CameraRepository.epis_obrigatorios_da_camera(camera.id)
        self._checkers[camera.id] = EPIChecker(epis_obrigatorios)
        self._contador_frames[camera.id] = 0

        config = CameraConfig(id=camera.id, nome=camera.nome, url_rtsp=camera.url_rtsp, fps_alvo=camera.fps_alvo)
        self.camera_manager.adicionar_camera(config, on_status_change=self._on_status_change)

    def parar_camera(self, camera_id: int) -> None:
        self.camera_manager.remover_camera(camera_id)
        self._checkers.pop(camera_id, None)

    def iniciar_todas(self, cameras: list[Camera]) -> None:
        for camera in cameras:
            if camera.ativa:
                self.iniciar_camera(camera)
        self.start_loop_processamento()

    def parar_tudo(self) -> None:
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=3)
        if self._batch_worker_thread:
            self._batch_worker_thread.join(timeout=3)
        self.camera_manager.parar_todas()

    # ------------------------------------------------------------------
    def start_loop_processamento(self) -> None:
        """Inicia as threads de monitoramento das câmeras e de inferência em lote."""
        if self._running:
            return
        self._running = True
        self._monitor_thread = threading.Thread(target=self._loop_processamento, daemon=True, name="pipeline-loop")
        self._batch_worker_thread = threading.Thread(target=self._loop_batch_inference, daemon=True, name="batch-worker")
        self._monitor_thread.start()
        self._batch_worker_thread.start()

    def _loop_processamento(self) -> None:
        intervalo = 1.0 / max(settings.camera.target_fps, 1)
        while self._running:
            for camera_id, stream in self.camera_manager.get_all_streams().items():
                if stream.status != StatusCamera.ONLINE:
                    continue

                self._contador_frames[camera_id] = self._contador_frames.get(camera_id, 0) + 1
                if self._contador_frames[camera_id] % settings.detection.frame_skip != 0:
                    continue  # aplica frame_skip para poupar CPU/GPU

                frame = stream.get_latest_frame()
                if frame is None:
                    continue

                try:
                    self._frame_queue.put_nowait((camera_id, frame, stream))
                except queue.Full:
                    pass  # descarta o frame se a fila estiver cheia para não acumular latência

            time.sleep(intervalo)

    # ------------------------------------------------------------------
    def _loop_batch_inference(self) -> None:
        """Thread consumidora que monta lotes de quadros e realiza inferência em lote na GPU/CPU."""
        while self._running:
            items = []
            t_inicio = time.time()
            while len(items) < self.batch_size and (time.time() - t_inicio) < self.timeout_sec:
                try:
                    item = self._frame_queue.get(timeout=0.005)
                    items.append(item)
                except queue.Empty:
                    break

            if not items:
                continue

            camera_ids = [it[0] for it in items]
            frames = [it[1] for it in items]
            streams = [it[2] for it in items]

            try:
                batch_deteccoes = self.detector.predict_batch(frames)
                for camera_id, frame, stream, deteccoes in zip(camera_ids, frames, streams, batch_deteccoes):
                    checker = self._checkers.get(camera_id)
                    if checker is None:
                        continue

                    resultado = checker.analisar(camera_id, frame, deteccoes)

                    if self._frame_callback:
                        self._frame_callback(camera_id, resultado)

                    if resultado.possui_infracao:
                        self._tratar_infracao(camera_id, resultado, stream)

            except Exception as e:
                logger.exception(f"Erro ao processar lote de inferência: {e}")
            checker = self._checkers.get(camera_id)
            if checker is None:
                return

            resultado = checker.analisar(camera_id, frame, deteccoes)

            if self._frame_callback:
                self._frame_callback(camera_id, resultado)

            if resultado.possui_infracao:
                self._tratar_infracao(camera_id, resultado, stream)

        except Exception as e:
            logger.exception(f"Erro ao processar frame da câmera {camera_id}: {e}")

    def _tratar_infracao(self, camera_id: int, resultado: ResultadoAnalise, stream) -> None:
        """Para cada pessoa não-conforme no frame, registra evento e dispara alerta."""
        camera = CameraRepository.buscar_por_id(camera_id)
        if camera is None:
            return

        for pessoa in resultado.pessoas:
            if pessoa.conforme:
                continue

            # Cooldown evita salvar evidência/alerta a cada frame de uma
            # mesma infração contínua.
            if not self.alert_service.pode_disparar(camera_id):
                continue

            snapshot_path = self.recording_service.salvar_snapshot(camera_id, resultado.frame_anotado)
            self.recording_service.gravar_clipe_async(camera_id, stream, fps=camera.fps_alvo)

            evento = EventService.registrar_evento(
                camera_id=camera_id,
                pessoa=pessoa,
                snapshot_path=snapshot_path,
            )

            self.alert_service.disparar_alerta(
                evento=evento,
                camera_nome=camera.nome,
                epis_ausentes=pessoa.epis_ausentes,
                snapshot_path=snapshot_path,
            )

    def _on_status_change(self, camera_id: int, status: StatusCamera) -> None:
        CameraRepository.atualizar_status(camera_id, status)
        if status == StatusCamera.ONLINE:
            EventService.registrar_evento_sistema(camera_id, TipoEvento.CAMERA_ONLINE, "Câmera reconectada.")
        elif status in (StatusCamera.OFFLINE, StatusCamera.ERRO):
            EventService.registrar_evento_sistema(camera_id, TipoEvento.CAMERA_OFFLINE, "Câmera indisponível.")
