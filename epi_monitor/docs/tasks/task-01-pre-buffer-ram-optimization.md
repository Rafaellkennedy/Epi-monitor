# Task 01: Otimização do Pre-Buffer e Consumo de RAM (Vazamento de Memória)

## 📌 Informações da Task & Git Flow

- **ID:** TASK-01
- **Título:** Otimização do Pre-Buffer de Vídeo e Controle de Memória RAM
- **Branch Recomendada:** `feature/fix-pre-buffer-ram-leak`
- **Base Branch:** `main` ou `develop`
- **Arquivos Afetados:**
  - [services/camera_service.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/services/camera_service.py)
  - [services/recording_service.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/services/recording_service.py)
  - [config/settings.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/config/settings.py)

---

## 🔴 1. O que está errado (Diagnóstico do Problema)

### Sintoma
Ao cadastrar e iniciar 10 ou mais câmeras simultâneas, a memória RAM do computador/servidor é consumida rapidamente até provocar travamento do sistema por **Out Of Memory (OOM)**.

### Causa Raiz
No arquivo [camera_service.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/services/camera_service.py#L75-L76), o objeto `CameraStream` armazena os frames dos últimos 5 segundos em uma lista Python (`self._pre_buffer`) na forma de objetos `numpy.ndarray` não comprimidos:

```python
# CÓDIGO ATUAL COM DEFEITO (camera_service.py)
def _atualizar_pre_buffer(self, frame: np.ndarray) -> None:
    agora = time.time()
    self._pre_buffer.append((agora, frame)) # Frame BGR cru uncompressed em RAM!
    limite = agora - self._pre_buffer_seconds
    self._pre_buffer = [(t, f) for (t, f) in self._pre_buffer if t >= limite]
```

### Cálculo do Impacto em RAM:
- 1 frame Full HD (1920x1080 em 3 canais BGR `uint8`) = `1920 * 1080 * 3 bytes` ≈ **6.2 MB**.
- A 10 FPS durante 5 segundos = **50 frames por câmera**.
- Memória consumida por câmera: `50 * 6.2 MB` ≈ **310 MB / câmera**.
- Em um cenário com 20 câmeras: `20 * 310 MB` ≈ **6.2 GB de RAM** alocados **apenas para manter o buffer pré-evento**!
- Além disso, a filtragem `[(t, f) for ...]` recria a lista a cada frame capturado (10 vezes por segundo), gerando centenas de alocações de lista por segundo que sobrecarregam o Garbage Collector (GC) do Python.

---

## 🟢 2. Caminho para a Solução (Guia de Refatoração)

### Estratégia de Refatoração:
1. **Compressão em Tempo Real (JPEG Buffer)**: Em vez de guardar a matriz `np.ndarray` crua, comprima o frame em um vetor de bytes JPEG (`cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])`) antes de inserir no pre-buffer.
   - Um frame JPEG comprimido com qualidade 80 ocupa apenas **~80 KB a 150 KB** (redução de mais de 95% do espaço em memória RAM!).
   - Consumo de 20 câmeras cai de **6.2 GB** para **~100 MB**!
2. **Uso de `collections.deque` com `maxlen`**: Substituir a lista comum por uma fila circular de tamanho fixo `deque(maxlen=N)`, evitando reconstruções contínuas de listas Python.
3. **Decodificação sob Demanda**: Quando houver disparo de infração e o `RecordingService` solicitar o pré-buffer (`get_pre_buffer()`), descomprima os bytes JPEG de volta para `np.ndarray` (`cv2.imdecode(jpg_bytes, cv2.IMREAD_COLOR)`).

### Passo a Passo de Código:

#### Alteração 1: `CameraStream.__init__` em [`services/camera_service.py`](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/services/camera_service.py#L75-L77)
```python
from collections import deque

# No __init__:
self._pre_buffer_max_frames = self.config.fps_alvo * self._pre_buffer_seconds
self._pre_buffer: deque[tuple[float, bytes]] = deque(maxlen=self._pre_buffer_max_frames)
```

#### Alteração 2: `_atualizar_pre_buffer` em [`services/camera_service.py`](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/services/camera_service.py#L166-L171)
```python
def _atualizar_pre_buffer(self, frame: np.ndarray) -> None:
    agora = time.time()
    # Comprime para JPEG em memória (Qualidade 80 é suficiente para clipes de auditoria)
    ok, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if ok:
        self._pre_buffer.append((agora, buffer.tobytes()))
```

#### Alteração 3: `get_pre_buffer` em [`services/camera_service.py`](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/services/camera_service.py#L161-L165)
```python
def get_pre_buffer(self) -> list[np.ndarray]:
    """Decodifica os frames comprimidos em memória apenas quando solicitado para salvar o vídeo."""
    frames_decodificados = []
    with self._lock:
        copia_buffer = list(self._pre_buffer)
    
    for _, jpg_bytes in copia_buffer:
        nparr = np.frombuffer(jpg_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is not None:
            frames_decodificados.append(img)
            
    return frames_decodificados
```

---

## 🧪 3. Plano de Testes (Antes de Fazer Merge)

### A. Teste Unitário (Automático com `pytest`)
Criar o arquivo `tests/test_camera_buffer.py`:

```python
import time
import numpy as np
import pytest
from services.camera_service import CameraStream, CameraConfig

def test_pre_buffer_ram_compression():
    config = CameraConfig(id=1, nome="Test Cam", url_rtsp="rtsp://dummy", fps_alvo=10)
    stream = CameraStream(config)
    
    # Gera 50 frames sintéticos HD (1920x1080)
    fake_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    
    for _ in range(50):
        stream._atualizar_pre_buffer(fake_frame)
        
    assert len(stream._pre_buffer) == 50
    
    # Verifica tamanho total ocupado em bytes na memória
    tamanho_total_bytes = sum(len(jpg_bytes) for _, jpg_bytes in stream._pre_buffer)
    tamanho_total_mb = tamanho_total_bytes / (1024 * 1024)
    
    # Deve ser menor que 5 MB (contra 310 MB da versão antiga)
    assert tamanho_total_mb < 5.0, f"Buffer ocupando {tamanho_total_mb:.2f} MB, esperava < 5MB"
    
    # Testa decodificação de volta
    frames_recuperados = stream.get_pre_buffer()
    assert len(frames_recuperados) == 50
    assert frames_recuperados[0].shape == (1080, 1920, 3)
```

### B. Teste de Carga e Estresse de Memória (Manual / Script)
Rodar o script de medição com `pytest`:
```bash
pytest tests/test_camera_buffer.py -v
```

---

## 🔀 4. Git Flow & Checklist de Pull Request (PR)

### Comandos Git para abrir a Branch:
```bash
git checkout main
git pull origin main
git checkout -b feature/fix-pre-buffer-ram-leak
```

### Mensagem de Commit Padronizada:
`fix(camera-service): compress pre-buffer frames to JPEG bytes to resolve RAM leak`

### Critérios para Aprovação do PR:
- [ ] O teste unitário `test_camera_buffer.py` passou 100%.
- [ ] O consumo de memória RAM para 20 streams simulados manteve-se abaixo de 500 MB.
- [ ] O salvamento de clipes de vídeo (`RecordingService._gravar_clipe`) continuou gerando arquivos `.mp4` válidos.
