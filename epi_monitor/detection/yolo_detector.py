"""
detection/yolo_detector.py
---------------------------
Encapsula o modelo YOLOv11 (Ultralytics) para realizar a inferência de
objetos em cada frame de vídeo. Esta classe é agnóstica de câmera/UI:
recebe um frame (numpy array BGR) e devolve uma lista de `Detection`.

Requisitos do modelo:
    O modelo (`epi_best.pt`) deve ser treinado/fine-tunado para reconhecer
    as classes definidas em `config.settings.DetectionSettings.class_names`,
    incluindo tanto o EPI presente ("capacete") quanto sua ausência
    ("sem_capacete") sempre que possível — isso melhora MUITO a precisão
    em relação a apenas detectar presença e inferir ausência por exclusão.

    Datasets públicos recomendados como ponto de partida para treino:
    "Hard Hat Workers Dataset", "Construction Site Safety Dataset" (Roboflow).

Resolução de classes (model-aware):
    a. Nome nativo do modelo no mapa de equivalência → nome interno EPI
    b. Classes fora do domínio EPI (ex: machinery, vehicle) → descartadas
    c. Fallback legado via dict class_names por id quando o mapa não bate
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

import numpy as np
import torch
from ultralytics import YOLO

from config.settings import settings
from models.detection import Detection, BoundingBox

logger = logging.getLogger(__name__)


def resolver_nome_classe(
    cls_id: int,
    native_names: dict,
    equivalence_map: dict[str, str],
    discard_classes: set[str],
    class_names_fallback: dict[int, str],
    is_fallback_model: bool = False,
) -> Optional[str]:
    """
    Função PURA e testável: resolve o nome da classe a partir do id
    retornado pelo modelo YOLO.

    Regras (em ordem):
      a. Se for modelo fallback COCO (yolo11n.pt), usa nomes nativos —
         sem aplicar mapeamentos EPI (evita falsos positivos).
      b. Se o nome nativo estiver no mapa de equivalência, retorna o
         nome interno EPI correspondente.
      c. Se o nome nativo estiver no conjunto de classes a descartar,
         retorna None (detecção ignorada).
      d. Fallback legado: usa dict `class_names` por id (para modelos
         customizados como `epi_best.pt`).
    """
    if is_fallback_model:
        return native_names.get(cls_id, f"classe_{cls_id}")

    native_name = native_names.get(cls_id, "")

    if native_name in equivalence_map:
        return equivalence_map[native_name]

    if native_name in discard_classes:
        return None  # descartar detecção

    # Fallback legado: dict id → nome (modelo customizado treinado)
    return class_names_fallback.get(cls_id, native_name or f"classe_{cls_id}")


class YoloDetector:
    """
    Wrapper single-model, thread-safe para leitura (Ultralytics libera
    inferência concorrente desde que cada thread não modifique o modelo).

    Uso:
        detector = YoloDetector()
        detections = detector.predict(frame_bgr)
    """

    _instance: "YoloDetector | None" = None

    def __init__(self) -> None:
        self.device = self._resolver_device(settings.detection.device)
        self.model_path = settings.detection.model_path
        self.confidence = settings.detection.confidence_threshold
        self.iou = settings.detection.iou_threshold
        self.img_size = settings.detection.img_size
        self.class_names = settings.detection.class_names
        self.epi_equivalence_map: dict[str, str] = settings.detection.epi_equivalence_map
        self.epi_discard_classes: set[str] = settings.detection.epi_discard_classes
        self._is_fallback_model: bool = False

        self._model: YOLO | None = None
        self._carregar_modelo()

    @classmethod
    def get_instance(cls) -> "YoloDetector":
        """Singleton: evita carregar o modelo (custoso) mais de uma vez em memória."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def _resolver_device(device_cfg: str) -> str:
        """Resolve 'auto' para 'cuda:0' se houver GPU NVIDIA disponível, senão 'cpu'."""
        if device_cfg != "auto":
            return device_cfg
        if torch.cuda.is_available():
            nome_gpu = torch.cuda.get_device_name(0)
            logger.info(f"GPU NVIDIA detectada: {nome_gpu}. Usando aceleração CUDA.")
            return "cuda:0"
        logger.warning("Nenhuma GPU NVIDIA disponível. Usando CPU (desempenho reduzido).")
        return "cpu"

    def _carregar_modelo(self) -> None:
        model_file = Path(self.model_path)
        if not model_file.exists():
            logger.warning(
                f"Modelo EPI não encontrado em '{self.model_path}'. "
                f"detecção de EPI desativada — fallback COCO (yolo11n.pt). "
                f"IMPORTANTE: treine um modelo específico de EPIs para uso em produção."
            )
            self._model = YOLO("yolo11n.pt")
            self._is_fallback_model = True
        else:
            self._model = YOLO(str(model_file))
            self._is_fallback_model = False

        try:
            self._model.to(self.device)
        except Exception as e:
            logger.error(f"Falha ao mover modelo para device '{self.device}': {e}. Usando CPU.")
            self.device = "cpu"
            self._model.to(self.device)

        logger.info(f"Modelo YOLO carregado ({self.model_path}) no device '{self.device}'.")

    def predict(self, frame: np.ndarray) -> List[Detection]:
        """
        Executa a inferência em um único frame BGR (formato OpenCV).
        Retorna a lista de detecções brutas (sem associação pessoa <-> EPI,
        isso é responsabilidade do EPIChecker).
        """
        if self._model is None:
            raise RuntimeError("Modelo YOLO não foi carregado corretamente.")

        results = self._model.predict(
            source=frame,
            conf=self.confidence,
            iou=self.iou,
            imgsz=self.img_size,
            device=self.device,
            verbose=False,
        )

        detections: List[Detection] = []
        if not results:
            return detections

        result = results[0]
        if result.boxes is None:
            return detections

        for box in result.boxes:
            cls_id = int(box.cls[0].item())
            nome_classe = resolver_nome_classe(
                cls_id=cls_id,
                native_names=result.names,
                equivalence_map=self.epi_equivalence_map,
                discard_classes=self.epi_discard_classes,
                class_names_fallback=self.class_names,
                is_fallback_model=self._is_fallback_model,
            )
            if nome_classe is None:
                continue  # descartar classes fora do domínio EPI

            conf = float(box.conf[0].item())
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

            detections.append(Detection(
                classe_id=cls_id,
                classe_nome=nome_classe,
                confianca=conf,
                bbox=BoundingBox(x1, y1, x2, y2),
            ))

        return detections

    def track(self, frame: np.ndarray) -> List[Detection]:
        """Inferência com rastreamento temporal (ByteTrack) ativado."""
        if self._model is None:
            raise RuntimeError("Modelo YOLO não foi carregado corretamente.")

        results = self._model.track(
            source=frame,
            conf=self.confidence,
            iou=self.iou,
            imgsz=self.img_size,
            device=self.device,
            persist=True,
            tracker="bytetrack.yaml",
            verbose=False,
        )

        detections: List[Detection] = []
        if not results or results[0].boxes is None:
            return detections

        result = results[0]
        for box in result.boxes:
            cls_id = int(box.cls[0].item())
            nome_classe = resolver_nome_classe(
                cls_id=cls_id,
                native_names=result.names,
                equivalence_map=self.epi_equivalence_map,
                discard_classes=self.epi_discard_classes,
                class_names_fallback=self.class_names,
                is_fallback_model=self._is_fallback_model,
            )
            if nome_classe is None:
                continue  # descartar classes fora do domínio EPI

            conf = float(box.conf[0].item())
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            track_id = int(box.id[0].item()) if box.id is not None else None

            detections.append(Detection(
                classe_id=cls_id,
                classe_nome=nome_classe,
                confianca=conf,
                bbox=BoundingBox(x1, y1, x2, y2),
                track_id=track_id,
            ))

        return detections

    def predict_batch(self, frames: List[np.ndarray]) -> List[List[Detection]]:
        """
        Executa a inferência em um LOTE de frames BGR simultaneamente na GPU/CPU.
        Retorna uma lista de listas de Detection (uma lista para cada frame do lote).
        """
        if self._model is None:
            raise RuntimeError("Modelo YOLO não foi carregado corretamente.")

        if not frames:
            return []

        results = self._model.predict(
            source=frames,
            conf=self.confidence,
            iou=self.iou,
            imgsz=self.img_size,
            device=self.device,
            verbose=False,
        )

        resultados_batch: List[List[Detection]] = []
        for result in results:
            detections: List[Detection] = []
            if result.boxes is not None:
                for box in result.boxes:
                    cls_id = int(box.cls[0].item())
                    nome_classe = resolver_nome_classe(
                        cls_id=cls_id,
                        native_names=result.names,
                        equivalence_map=self.epi_equivalence_map,
                        discard_classes=self.epi_discard_classes,
                        class_names_fallback=self.class_names,
                        is_fallback_model=self._is_fallback_model,
                    )
                    if nome_classe is None:
                        continue  # descartar classes fora do domínio EPI

                    conf = float(box.conf[0].item())
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

                    detections.append(Detection(
                        classe_id=cls_id,
                        classe_nome=nome_classe,
                        confianca=conf,
                        bbox=BoundingBox(x1, y1, x2, y2),
                    ))
            resultados_batch.append(detections)

        return resultados_batch

    def reload_model(self, new_path: str | None = None) -> None:
        """Permite trocar o modelo em tempo de execução (ex.: após retreinar)."""
        if new_path:
            self.model_path = new_path
        self._carregar_modelo()
