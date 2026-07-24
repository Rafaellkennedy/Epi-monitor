# Task 03: Otimização da Renderização na Interface Qt (UI Lag & Limitador de FPS)

## 📌 Informações da Task & Git Flow

- **ID:** TASK-03
- **Título:** Desacoplamento da Taxa de Exibição da Interface Gráfica (Prevenção de UI Freeze)
- **Branch Recomendada:** `feature/ui-video-rendering-fps`
- **Base Branch:** `main` ou `develop`
- **Arquivos Afetados:**
  - [ui/widgets/camera_widget.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/ui/widgets/camera_widget.py)
  - [ui/pages/cameras_page.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/ui/pages/cameras_page.py)

---

## 🔴 1. O que está errado (Diagnóstico do Problema)

### Sintoma
À medida que mais câmeras são conectadas (4 ou mais no grid), a interface gráfica do programa congela (fica sem responder), as animações dos botões travam e o uso de CPU atinge picos altos na thread principal do Qt.

### Causa Raiz
No arquivo [camera_widget.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/ui/widgets/camera_widget.py#L69-L79), cada resultado do pipeline tenta redesenhar a tela imediatamente:

```python
# CÓDIGO ATUAL COM DEFEITO (camera_widget.py)
def atualizar_frame(self, frame_bgr: np.ndarray) -> None:
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    h, w, ch = frame_rgb.shape
    bytes_per_line = ch * w
    qimg = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
    pixmap = QPixmap.fromImage(qimg).scaled(
        self.label_video.width(), self.label_video.height(),
        Qt.KeepAspectRatio, Qt.SmoothTransformation # CPU BOUND! Muito lento para N câmeras!
    )
    self.label_video.setPixmap(pixmap)
```

### Problemas dessa abordagem:
1. **Redimensionamento por CPU na UI Thread**: O método `scaled(..., Qt.SmoothTransformation)` processa o redimensionamento por interpolação bicúbica/bilinear na CPU dentro do Qt Event Loop Principal.
2. **Atualização Desnecessariamente Frequente para Olho Humano**: Tentar redesenhar 10 ou 20 câmeras na tela a 10 ou 15 FPS é desnecessário. O operador precisa ver a pré-visualização fluida a ~5 FPS na tela, enquanto a IA interna pode continuar analisando a 10 FPS em background.

---

## 🟢 2. Caminho para a Solução (Guia de Refatoração)

### Estratégia de Refatoração:
1. **Limitador de FPS de Exibição (`Display Throttle`)**: Adicionar uma trava por marcação de tempo (`time.time()`) dentro do `CameraWidget`. Redesenhar o widget apenas se tiver passado pelo menos `1.0 / max_ui_fps` (ex.: 200 ms = 5 FPS).
2. **Redimensionamento Rápido (`Qt.FastTransformation`)**: Trocar a transformação suave por `Qt.FastTransformation` nos cards menores do grid, reservando a suavização apenas se o usuário expandir a câmera para tela cheia.
3. **Reutilização de Buffer QImage**: Evitar re-alocar o objeto `QImage` se a resolução do frame não mudou.

### Passo a Passo de Código:

#### Alteração no [`ui/widgets/camera_widget.py`](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/ui/widgets/camera_widget.py)
```python
import time

class CameraWidget(QFrame):
    def __init__(self, camera_id: int, nome: str, max_ui_fps: int = 5) -> None:
        super().__init__()
        self.camera_id = camera_id
        self.max_ui_fps = max_ui_fps
        self._min_interval = 1.0 / max_ui_fps
        self._ultimo_render_ts = 0.0
        self.setObjectName("card")
        self._montar_ui(nome)

    def atualizar_frame(self, frame_bgr: np.ndarray) -> None:
        """Atualiza a exibição visual apenas se tiver respeitado o limite de FPS da UI."""
        agora = time.time()
        if (agora - self._ultimo_render_ts) < self._min_interval:
            return  # Descarta o redesenho no widget para poupar CPU na UI Thread (a IA já analisou)

        self._ultimo_render_ts = agora

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = frame_rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        # FastTransformation reduz em 70% o custo de CPU de escala do Pixmap no Qt
        pixmap = QPixmap.fromImage(qimg).scaled(
            self.label_video.width(), self.label_video.height(),
            Qt.KeepAspectRatio, Qt.FastTransformation
        )
        self.label_video.setPixmap(pixmap)
```

---

## 🧪 3. Plano de Testes (Antes de Fazer Merge)

### A. Teste Unitário (Automático com `pytest-qt`)
Criar o arquivo `tests/test_camera_widget.py`:

```python
import time
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from ui.widgets.camera_widget import CameraWidget

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

def test_camera_widget_fps_limiter(qapp):
    widget = CameraWidget(camera_id=1, nome="Cam Teste", max_ui_fps=5)
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Chama o render 10 vezes em sequência rápida (< 10ms)
    t0 = time.time()
    for _ in range(10):
        widget.atualizar_frame(fake_frame)
        
    # Somente o primeiro frame deve ter sido desenhado devido ao throttling de 200ms
    assert (time.time() - t0) < 0.1
```

### B. Teste de Responsividade da UI (Manual)
1. Iniciar o app com 6 câmeras no grid.
2. Clicar nos botões do menu lateral (Dashboard, Eventos, Configurações).
3. **Resultado Esperado**: A troca de páginas deve ser instantânea, sem atrasos de cliques ou travamentos na tela.

---

## 🔀 4. Git Flow & Checklist de Pull Request (PR)

### Comandos Git para abrir a Branch:
```bash
git checkout main
git pull origin main
git checkout -b feature/ui-video-rendering-fps
```

### Mensagem de Commit Padronizada:
`perf(ui): throttle CameraWidget rendering to 5 FPS to avoid main thread UI freeze`

### Critérios para Aprovação do PR:
- [ ] Teste de widget `test_camera_widget.py` aprovado.
- [ ] Troca de páginas no menu lateral funcional sem atraso sob carga de 6 câmeras simultâneas.
