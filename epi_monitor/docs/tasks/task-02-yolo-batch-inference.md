# Task 02: Refatoração do Pipeline de Inferência YOLO (GIL & Batch Inference)

## 📌 Informações da Task & Git Flow

- **ID:** TASK-02
- **Título:** Otimização do Pipeline de IA com Fila Assíncrona e Inferência em Lote (Batch Inference)
- **Branch Recomendada:** `feature/yolo-batch-inference`
- **Base Branch:** `main` ou `develop`
- **Arquivos Afetados:**
  - [services/detection_pipeline.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/services/detection_pipeline.py)
  - [detection/yolo_detector.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/detection/yolo_detector.py)

---

## 🔴 1. O que está errado (Diagnóstico do Problema)

### Sintoma
Quando várias câmeras (10+) estão ativas, a taxa de quadros (FPS) despenca, a CPU fica em 100% de uso e a GPU NVIDIA apresenta baixo aproveitamento (<30%), com picos imprevisíveis de latência.

### Causa Raiz
No arquivo [detection_pipeline.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/services/detection_pipeline.py#L67), as chamadas de inferência do YOLO usam `ThreadPoolExecutor`:

```python
# CÓDIGO ATUAL COM DEFEITO (detection_pipeline.py)
self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="inferencia")
...
# Submete cada frame individualmente para uma thread do pool:
self._executor.submit(self._processar_frame, camera_id, frame, stream)
```

### Problemas dessa abordagem:
1. **Trava do GIL (Global Interpreter Lock)**: No CPython, o pré-processamento das matrizes OpenCV/NumPy e a conversão de tensores `torch.from_numpy()` são executados sob a trava do GIL. Várias threads disputando o GIL desaceleram o processamento em vez de acelerá-lo.
2. **Subaproveitamento da GPU (Batch Size = 1)**: Executar `model.predict(frame)` com 1 único frame por vez desperdiça a paralelização massiva de núcleos Tensor Cores das GPUs NVIDIA. GPUs são otimizadas para processar matrizes em lotes (batching: `[batch_size, 3, 640, 640]`).

---

## 🟢 2. Caminho para a Solução (Guia de Refatoração)

### Estratégia de Refatoração:
1. **Implementar Fila de Inferência (`queue.Queue`)**: Em vez de `ThreadPoolExecutor`, utilizar uma fila thread-safe onde todas as câmeras depositam seus frames mais recentes.
2. **Worker de Inferência em Lote (`Batch Inference Worker`)**: Criar uma thread dedicada consumindo da fila. Quando houver N frames na fila (ou atingir um timeout de 15ms), reunir os frames em uma lista `[frame_1, frame_2, ...]` e chamar `detector.predict_batch(frames)`.
3. **Suporte a Lote no `YoloDetector`**: Atualizar o método de predição para receber uma lista de frames e retornar uma lista de lista de detecções.

### Passo a Passo de Código:

#### Alteração 1: `YoloDetector.predict_batch` em [`detection/yolo_detector.py`](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/detection/yolo_detector.py#L100)
```python
def predict_batch(self, frames: list[np.ndarray]) -> list[list[Detection]]:
    """
    Executa a inferência em um LOTE de frames BGR simultaneamente na GPU.
    Retorna uma lista de listas de Detection (uma lista de detecção para cada frame do lote).
    """
    if not frames:
        return []

    results = self._model.predict(
        source=frames,  # Passar lista de frames para atuar em lote na GPU
        conf=self.confidence,
        iou=self.iou,
        imgsz=self.img_size,
        device=self.device,
        verbose=False,
    )

    resultados_batch: list[list[Detection]] = []
    for result in results:
        detections: list[Detection] = []
        if result.boxes is not None:
            for box in result.boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                nome_classe = self.class_names.get(cls_id, result.names.get(cls_id, f"classe_{cls_id}"))

                detections.append(Detection(
                    classe_id=cls_id,
                    classe_nome=nome_classe,
                    confianca=conf,
                    bbox=BoundingBox(x1, y1, x2, y2),
                ))
        resultados_batch.append(detections)

    return resultados_batch
```

#### Alteração 2: Loop de Fila no [`services/detection_pipeline.py`](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/services/detection_pipeline.py)
```python
import queue

class DetectionPipeline:
    def __init__(self, camera_manager, alert_service, batch_size: int = 4, timeout_ms: float = 0.015):
        self.camera_manager = camera_manager
        self.alert_service = alert_service
        self.detector = YoloDetector.get_instance()
        self.batch_size = batch_size
        self.timeout_sec = timeout_ms
        
        self._frame_queue: queue.Queue = queue.Queue(maxsize=100)
        self._worker_thread: Optional[threading.Thread] = None

    def _loop_batch_inference(self) -> None:
        """Thread consumidora que monta lotes e faz a inferência otimizada."""
        while self._running:
            items = []
            # Coleta até batch_size itens da fila dentro da janela de tempo
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

            # Inferência em lote na GPU
            batch_deteccoes = self.detector.predict_batch(frames)

            # Processa o resultado de cada câmera
            for camera_id, frame, stream, deteccoes in zip(camera_ids, frames, streams, batch_deteccoes):
                checker = self._checkers.get(camera_id)
                if checker:
                    resultado = checker.analisar(camera_id, frame, deteccoes)
                    if self._frame_callback:
                        self._frame_callback(camera_id, resultado)
                    if resultado.possui_infracao:
                        self._tratar_infracao(camera_id, resultado, stream)
```

---

## 🧪 3. Plano de Testes (Antes de Fazer Merge)

### A. Teste Unitário (Automático com `pytest`)
Criar o arquivo `tests/test_yolo_batch.py`:

```python
import numpy as np
import pytest
from detection.yolo_detector import YoloDetector

def test_predict_batch():
    detector = YoloDetector.get_instance()
    
    # Cria 4 frames pretos sintéticos
    f1 = np.zeros((640, 640, 3), dtype=np.uint8)
    f2 = np.zeros((640, 640, 3), dtype=np.uint8)
    f3 = np.zeros((640, 640, 3), dtype=np.uint8)
    f4 = np.zeros((640, 640, 3), dtype=np.uint8)
    
    batch = [f1, f2, f3, f4]
    resultados = detector.predict_batch(batch)
    
    assert len(resultados) == 4
    assert isinstance(resultados[0], list)
```

### B. Benchmark de Desempenho (FPS)
Comparar tempo de inferência individual vs inferência em lote:
```bash
pytest tests/test_yolo_batch.py -v
```

---

## 🔀 4. Git Flow & Checklist de Pull Request (PR)

### Comandos Git para abrir a Branch:
```bash
git checkout main
git pull origin main
git checkout -b feature/yolo-batch-inference
```

### Mensagem de Commit Padronizada:
`feat(pipeline): replace ThreadPoolExecutor with async queue and YOLO batch inference`

### Critérios para Aprovação do PR:
- [ ] Teste unitário `test_yolo_batch.py` aprovado.
- [ ] O throughput total de inferência (FPS global) aumentou em pelo menos 40% com 8 câmeras simultâneas.
- [ ] Nenhuma colisão ou exceção `CUDA out of memory` reportada durante a execução contínua de 10 minutos.
