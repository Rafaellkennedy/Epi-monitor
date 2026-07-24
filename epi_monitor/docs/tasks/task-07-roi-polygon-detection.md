# Task 07: Filtragem por Região de Interesse (Polígono ROI por Câmera)

## 📌 Informações da Task & Git Flow

- **ID:** TASK-07
- **Título:** Filtragem de Detecção por Polígono de Região de Interesse (ROI)
- **Branch Recomendada:** `feature/roi-polygon-detection`
- **Base Branch:** `main` ou `develop`
- **Arquivos Afetados:**
  - [detection/epi_checker.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/detection/epi_checker.py)
  - [services/camera_repository.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/services/camera_repository.py)

---

## 🔴 1. O que está errado (Diagnóstico do Problema)

### Sintoma
Trabalhadores caminhando na calçada externa, carros na rua de acesso ou pessoas na área administrativa ao fundo da câmera geram infrações de EPI desnecessárias.

### Causa Raiz
No arquivo [epi_checker.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/detection/epi_checker.py#L73-L80), a análise processa todas as pessoas detectadas no quadro inteiro. A coluna `zona_deteccao_json` da tabela `cameras` armazena o polígono configurado para a área de risco, mas essa informação é **completamente ignorada** pelo código de checagem.

---

## 🟢 2. Caminho para a Solução (Guia de Refatoração)

### Estratégia de Refatoração:
1. **Passar a ROI para o `EPIChecker`**: Ao instanciar ou atualizar o `EPIChecker`, passar a lista de pontos do polígono ROI `[ (x1,y1), (x2,y2), ... ]`.
2. **Filtrar Pessoas Fora do Polígono (`cv2.pointPolygonTest`)**: Para cada pessoa detectada, verificar se o ponto central da caixa delimitadora está dentro do polígono ROI usando OpenCV `cv2.pointPolygonTest(poligono, ponto_centro, measureDist=False) >= 0`.
3. Descarta pessoas que estejam fora da área delimitada antes de rodar a checagem de EPIs.

### Passo a Passo de Código:

#### Alteração em [`detection/epi_checker.py`](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/detection/epi_checker.py)
```python
import json
import cv2
import numpy as np

class EPIChecker:
    def __init__(self, epis_obrigatorios: list[TipoEPI], zona_roi_json: str | None = None):
        self.epis_obrigatorios = epis_obrigatorios
        self.poligono_roi: np.ndarray | None = self._parse_roi(zona_roi_json)

    def _parse_roi(self, zona_json: str | None) -> np.ndarray | None:
        if not zona_json:
            return None
        try:
            pontos = json.loads(zona_json)  # Ex: [[100, 100], [500, 100], [500, 400], [100, 400]]
            return np.array(pontos, dtype=np.int32)
        except Exception:
            return None

    def _pessoa_dentro_da_roi(self, bbox_pessoa: BoundingBox) -> bool:
        if self.poligono_roi is None:
            return True  # Se não houver ROI definida, considera a imagem inteira

        centro_x = (bbox_pessoa.x1 + bbox_pessoa.x2) / 2.0
        centro_y = (bbox_pessoa.y1 + bbox_pessoa.y2) / 2.0
        
        # Teste de ponto dentro do polígono em OpenCV
        res = cv2.pointPolygonTest(self.poligono_roi, (centro_x, centro_y), False)
        return res >= 0

    def analisar(self, camera_id: int, frame: np.ndarray, deteccoes: list[Detection]) -> ResultadoAnalise:
        pessoas_det = [d for d in deteccoes if d.classe_nome == "pessoa"]
        
        # Filtra apenas pessoas dentro da zona de risco (ROI)
        pessoas_na_roi = [p for p in pessoas_det if self._pessoa_dentro_da_roi(p.bbox)]
        
        # ... (segue análise apenas para pessoas_na_roi) ...
```

---

## 🧪 3. Plano de Testes (Antes de Fazer Merge)

### A. Teste Unitário (`tests/test_roi_filter.py`)
```python
import pytest
import json
import numpy as np
from detection.epi_checker import EPIChecker
from models.detection import Detection, BoundingBox
from models.enums import TipoEPI

def test_filtro_roi_poligono():
    # Define polígono quadrado de (100,100) até (300,300)
    roi_json = json.dumps([[100, 100], [300, 100], [300, 300], [100, 300]])
    checker = EPIChecker(epis_obrigatorios=[TipoEPI.CAPACETE], zona_roi_json=roi_json)
    
    # Pessoa 1: Centro (200, 200) -> Dentro da ROI
    p1 = Detection(0, "pessoa", 0.9, BoundingBox(150, 150, 250, 250))
    
    # Pessoa 2: Centro (500, 500) -> Fora da ROI
    p2 = Detection(0, "pessoa", 0.9, BoundingBox(450, 450, 550, 550))
    
    fake_frame = np.zeros((600, 600, 3), dtype=np.uint8)
    resultado = checker.analisar(1, fake_frame, [p1, p2])
    
    # Apenas a pessoa 1 deve ser analisada
    assert len(resultado.pessoas) == 1
    assert resultado.pessoas[0].bbox_pessoa.x1 == 150
```

---

## 🔀 4. Git Flow & Checklist de Pull Request (PR)

### Comandos Git para abrir a Branch:
```bash
git checkout main
git pull origin main
git checkout -b feature/roi-polygon-detection
```

### Mensagem de Commit Padronizada:
`feat(detection): add polygon ROI filtering in EPIChecker to exclude background areas`

### Critérios para Aprovação do PR:
- [ ] Teste unitário `test_roi_filter.py` aprovado.
- [ ] Detecções fora do polígono ROI ignoradas corretamente durante simulação de vídeo.
