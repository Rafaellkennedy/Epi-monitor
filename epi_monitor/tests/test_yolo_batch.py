import pytest
import numpy as np
from detection.yolo_detector import YoloDetector


def test_predict_batch():
    """Testa a execução de inferência em lote (batch inference) no YoloDetector."""
    detector = YoloDetector.get_instance()

    # Cria 4 quadros sintéticos (640x640)
    f1 = np.zeros((640, 640, 3), dtype=np.uint8)
    f2 = np.zeros((640, 640, 3), dtype=np.uint8)
    f3 = np.zeros((640, 640, 3), dtype=np.uint8)
    f4 = np.zeros((640, 640, 3), dtype=np.uint8)

    batch = [f1, f2, f3, f4]
    resultados = detector.predict_batch(batch)

    # Verifica se retornou 4 listas de detecções (uma por frame)
    assert len(resultados) == 4
    assert isinstance(resultados[0], list)
    assert isinstance(resultados[1], list)
