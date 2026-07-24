# Task 04: Integração de Object Tracking (ByteTrack) e Persistência Temporal (Debounce)

## 📌 Informações da Task & Git Flow

- **ID:** TASK-04
- **Título:** Habilitação de Rastreamento de Objetos (ByteTrack) e Filtro de Persistência de Infrações
- **Branch Recomendada:** `feature/bytetrack-temporal-debounce`
- **Base Branch:** `main` ou `develop`
- **Arquivos Afetados:**
  - [detection/yolo_detector.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/detection/yolo_detector.py)
  - [detection/epi_checker.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/detection/epi_checker.py)

---

## 🔴 1. O que está errado (Diagnóstico do Problema)

### Sintoma
O sistema gera muitos **falsos alarmes de infração**. Quando um funcionário devidamente equipado vira a cabeça de lado por um único segundo, a câmera perde o ângulo dos óculos/capacete por 1 quadro e dispara alarme sonoro, envia e-mail e grava evidência.

### Causa Raiz
No arquivo [epi_checker.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/detection/epi_checker.py#L111-L115), a decisão de infração é instantânea e baseada em uma foto estática isolada (single frame):

```python
# CÓDIGO ATUAL COM DEFEITO (epi_checker.py)
# Se em 1 único frame o EPI não for visto, a pessoa é considerada não-conforme imediatamente:
pessoa.epis_ausentes = ausentes
pessoa.conforme = len(ausentes) == 0
```

### Problemas dessa abordagem:
1. **Sem Histórico Temporal (`track_id`)**: O sistema trata cada frame como se fosse de uma pessoa completamente nova. Não sabe se a pessoa no frame N é a mesma pessoa que estava no frame N-1.
2. **Vulnerabilidade a Oclusões Momentâneas**: Iluminação, reflexo ou ângulo temporário causam falsas detecções de ausência se não houver um filtro de contagem (debounce).

---

## 🟢 2. Caminho para a Solução (Guia de Refatoração)

### Estratégia de Refatoração:
1. **Habilitar Tracking no YOLO (ByteTrack)**: Usar `model.track(..., persist=True, tracker="bytetrack.yaml")` no `YoloDetector` para que cada pessoa receba um `track_id` numérico consistente ao se mover pela imagem.
2. **Filtro de Debounce Temporal no `EPIChecker`**:
   - Manter um dicionário de histórico por `track_id`: `self._historico_infracoes[track_id] = contador`.
   - Se a pessoa for vista sem capacete por **30 segundos** (isso deve ser configurável), aí sim confirmar a infração.
   - Se a pessoa reaparecer conforme, zerar o contador do `track_id`.

### Passo a Passo de Código:

#### Alteração 1: `YoloDetector.track` em [`detection/yolo_detector.py`](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/detection/yolo_detector.py)
```python
def track(self, frame: np.ndarray) -> list[Detection]:
    """Inferência com rastreamento temporal (ByteTrack) ativado."""
    if self._model is None:
        raise RuntimeError("Modelo YOLO não foi carregado.")

    results = self._model.track(
        source=frame,
        conf=self.confidence,
        iou=self.iou,
        imgsz=self.img_size,
        device=self.device,
        persist=True,  # Mantém o rastreador entre chamadas consecutivas
        tracker="bytetrack.yaml",
        verbose=False,
    )

    detections: list[Detection] = []
    if not results or results[0].boxes is None:
        return detections

    result = results[0]
    for box in result.boxes:
        cls_id = int(box.cls[0].item())
        conf = float(box.conf[0].item())
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        
        # Pega o ID de rastreamento se atribuído pelo ByteTrack
        track_id = int(box.id[0].item()) if box.id is not None else None
        nome_classe = self.class_names.get(cls_id, result.names.get(cls_id, f"classe_{cls_id}"))

        detections.append(Detection(
            classe_id=cls_id,
            classe_nome=nome_classe,
            confianca=conf,
            bbox=BoundingBox(x1, y1, x2, y2),
            track_id=track_id
        ))

    return detections
```

#### Alteração 2: Debounce em [`detection/epi_checker.py`](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/detection/epi_checker.py)
```python
class EPIChecker:
    def __init__(self, epis_obrigatorios: list[TipoEPI], min_frames_infracao: int = 3):
        self.epis_obrigatorios = epis_obrigatorios
        self.min_frames_infracao = min_frames_infracao
        # {track_id: contagem_frames_sem_epi}
        self._contador_infracoes_por_track: dict[int, int] = {}

    def analisar(self, camera_id: int, frame: np.ndarray, deteccoes: list[Detection]) -> ResultadoAnalise:
        # ... (processamento de bboxes) ...
        
        for pessoa in pessoas_analisadas:
            tem_ausencia = len(ausentes) > 0
            t_id = pessoa.track_id

            if t_id is not None:
                if tem_ausencia:
                    self._contador_infracoes_por_track[t_id] = self._contador_infracoes_por_track.get(t_id, 0) + 1
                else:
                    self._contador_infracoes_por_track[t_id] = 0

                # Só confirma infração se a falta do EPI persistiu por N quadros consecutivos
                confirmado_infracao = self._contador_infracoes_por_track[t_id] >= self.min_frames_infracao
            else:
                confirmado_infracao = tem_ausencia  # Fallback sem tracking

            pessoa.epis_ausentes = ausentes if confirmado_infracao else []
            pessoa.conforme = not confirmado_infracao
```

---

## 🧪 3. Plano de Testes (Antes de Fazer Merge)

### A. Teste Unitário (Automático com `pytest`)
Criar o arquivo `tests/test_epi_checker_debounce.py`:

```python
import numpy as np
import pytest
from detection.epi_checker import EPIChecker
from models.detection import Detection, BoundingBox
from models.enums import TipoEPI

def test_debounce_infracao_temporal():
    checker = EPIChecker(epis_obrigatorios=[TipoEPI.CAPACETE], min_frames_infracao=3)
    
    # Detecção de pessoa sem capacete com track_id = 10
    det_pessoa = Detection(classe_id=0, classe_nome="pessoa", confianca=0.9, 
                           bbox=BoundingBox(0, 0, 100, 100), track_id=10)
    fake_frame = np.zeros((200, 200, 3), dtype=np.uint8)
    
    # Frame 1: Sem capacete -> não deve ser infração confirmada ainda (contagem = 1)
    res1 = checker.analisar(1, fake_frame, [det_pessoa])
    assert res1.pessoas[0].conforme is True
    
    # Frame 2: Sem capacete -> não deve ser infração confirmada ainda (contagem = 2)
    res2 = checker.analisar(1, fake_frame, [det_pessoa])
    assert res2.pessoas[0].conforme is True
    
    # Frame 3: Sem capacete -> AGORA deve confirmar infração! (contagem = 3)
    res3 = checker.analisar(1, fake_frame, [det_pessoa])
    assert res3.pessoas[0].conforme is False
    assert TipoEPI.CAPACETE in res3.pessoas[0].epis_ausentes
```

---

## 🔀 4. Git Flow & Checklist de Pull Request (PR)

### Comandos Git para abrir a Branch:
```bash
git checkout main
git pull origin main
git checkout -b feature/bytetrack-temporal-debounce
```

### Mensagem de Commit Padronizada:
`feat(detection): integrate ByteTrack and add 3-frame temporal debounce filter`

### Critérios para Aprovação do PR:
- [ ] Teste unitário `test_epi_checker_debounce.py` aprovado.
- [ ] Oclusões de 1 frame de duração não disparam alarme sonoro nem notificam a UI.
