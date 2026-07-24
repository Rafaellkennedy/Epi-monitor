"""
detection/epi_checker.py
--------------------------
Responsável por transformar as detecções BRUTAS do YOLO (lista plana de
boxes: pessoa, capacete, sem_capacete, colete...) em um resultado de
domínio (`ResultadoAnalise`) que diz, PARA CADA PESSOA no frame, quais
EPIs obrigatórios estão faltando.

Estratégia de associação pessoa <-> EPI:
    Como o YOLO detecta cada objeto separadamente, usamos sobreposição
    espacial (IoU) e centro-dentro-da-bbox para associar cada detecção de
    EPI à pessoa mais provável. Isso é suficiente para cenários com poucas
    pessoas por câmera; para cenas muito populosas, recomenda-se acoplar
    um tracker (ByteTrack, já integrado ao Ultralytics via `model.track()`).
"""

from __future__ import annotations

import datetime
import time
from typing import Dict, List, Optional

import cv2
import numpy as np

from models.detection import Detection, BoundingBox, PessoaAnalisada, ResultadoAnalise
from models.enums import TipoEPI

# Mapeia o nome de classe do modelo -> TipoEPI de domínio.
# Classes "sem_*" indicam AUSÊNCIA explícita (o modelo foi treinado para
# reconhecer isso diretamente, o que é mais confiável que inferir por exclusão).
_CLASSE_PARA_EPI = {
    "capacete": TipoEPI.CAPACETE,
    "oculos": TipoEPI.OCULOS,
    "colete": TipoEPI.COLETE,
    "mascara": TipoEPI.MASCARA,
    "luvas": TipoEPI.LUVAS,
}
_CLASSE_AUSENCIA = {
    "sem_capacete": TipoEPI.CAPACETE,
    "sem_oculos": TipoEPI.OCULOS,
    "sem_colete": TipoEPI.COLETE,
    "sem_mascara": TipoEPI.MASCARA,
    "sem_luvas": TipoEPI.LUVAS,
}

# Cores (BGR) para desenho das caixas
_COR_OK = (46, 204, 113)       # verde
_COR_INFRACAO = (0, 0, 255)    # vermelho
_COR_EPI = (255, 191, 0)       # azul claro


def _centro(bbox: BoundingBox) -> tuple[float, float]:
    return ((bbox.x1 + bbox.x2) / 2, (bbox.y1 + bbox.y2) / 2)


def _ponto_dentro_bbox(ponto: tuple[float, float], bbox: BoundingBox, margem: int = 15) -> bool:
    x, y = ponto
    return (bbox.x1 - margem) <= x <= (bbox.x2 + margem) and (bbox.y1 - margem) <= y <= (bbox.y2 + margem)


class EPIChecker:
    """Analisa detecções brutas e determina conformidade por pessoa com debounce temporal em segundos."""

    def __init__(self, epis_obrigatorios: List[TipoEPI], min_segundos_infracao: float = 30.0):
        """
        Args:
            epis_obrigatorios: lista de EPIs que DEVEM estar presentes nesta câmera.
            min_segundos_infracao: tempo contínuo em segundos (default: 30s) sem o EPI
                                   necessário para confirmar a infração (debounce temporal).
        """
        self.epis_obrigatorios = epis_obrigatorios
        self.min_segundos_infracao = min_segundos_infracao
        # {track_id: timestamp_primeira_deteccao_sem_epi}
        self._primeiro_timestamp_infracao: Dict[int, float] = {}

    def analisar(self, camera_id: int, frame: np.ndarray, deteccoes: List[Detection]) -> ResultadoAnalise:
        pessoas_det = [d for d in deteccoes if d.classe_nome == "pessoa"]
        epis_det = [d for d in deteccoes if d.classe_nome in _CLASSE_PARA_EPI or d.classe_nome in _CLASSE_AUSENCIA]

        # Se o modelo não detecta a classe "pessoa" separadamente (alguns
        # modelos customizados só detectam os EPIs), tratamos o frame
        # inteiro como "uma pessoa" para não perder a análise.
        if not pessoas_det and epis_det:
            altura, largura = frame.shape[:2]
            pessoas_det = [Detection(
                classe_id=-1, classe_nome="pessoa", confianca=1.0,
                bbox=BoundingBox(0, 0, largura, altura)
            )]

        pessoas_analisadas: List[PessoaAnalisada] = []
        agora = time.time()

        for pessoa_det in pessoas_det:
            pessoa = PessoaAnalisada(bbox_pessoa=pessoa_det.bbox, track_id=pessoa_det.track_id)
            epis_presentes_pessoa: set[TipoEPI] = set()
            epis_ausentes_explicitos: set[TipoEPI] = set()

            for epi_d in epis_det:
                centro_epi = _centro(epi_d.bbox)
                if not _ponto_dentro_bbox(centro_epi, pessoa_det.bbox):
                    continue

                pessoa.epis_detectados.append(epi_d)
                if epi_d.classe_nome in _CLASSE_PARA_EPI:
                    epis_presentes_pessoa.add(_CLASSE_PARA_EPI[epi_d.classe_nome])
                elif epi_d.classe_nome in _CLASSE_AUSENCIA:
                    epis_ausentes_explicitos.add(_CLASSE_AUSENCIA[epi_d.classe_nome])

            # Determina EPIs ausentes: é ausente se (a) o modelo detectou
            # explicitamente a ausência, OU (b) é obrigatório e não foi
            # detectada presença nenhuma (fallback por exclusão).
            ausentes: List[TipoEPI] = []
            for epi_obrig in self.epis_obrigatorios:
                sem_presenca = epi_obrig not in epis_presentes_pessoa
                ausencia_explicita = epi_obrig in epis_ausentes_explicitos
                if ausencia_explicita or sem_presenca:
                    ausentes.append(epi_obrig)

            tem_ausencia = len(ausentes) > 0
            t_id = pessoa.track_id

            if t_id is not None:
                if tem_ausencia:
                    if t_id not in self._primeiro_timestamp_infracao:
                        self._primeiro_timestamp_infracao[t_id] = agora

                    tempo_decorrido = agora - self._primeiro_timestamp_infracao[t_id]
                    confirmado_infracao = tempo_decorrido >= self.min_segundos_infracao
                else:
                    self._primeiro_timestamp_infracao.pop(t_id, None)
                    confirmado_infracao = False
            else:
                confirmado_infracao = tem_ausencia  # Fallback sem tracking

            pessoa.epis_ausentes = ausentes if confirmado_infracao else []
            pessoa.conforme = not confirmado_infracao
            pessoas_analisadas.append(pessoa)

        frame_anotado = self._desenhar_anotacoes(frame.copy(), pessoas_analisadas)

        return ResultadoAnalise(
            camera_id=camera_id,
            timestamp=datetime.datetime.now(),
            frame_anotado=frame_anotado,
            pessoas=pessoas_analisadas,
        )

    @staticmethod
    def _desenhar_anotacoes(frame: np.ndarray, pessoas: List[PessoaAnalisada]) -> np.ndarray:
        """Desenha as caixas delimitadoras, rótulos e % de confiança no frame."""
        for pessoa in pessoas:
            cor = _COR_OK if pessoa.conforme else _COR_INFRACAO
            bp = pessoa.bbox_pessoa
            cv2.rectangle(frame, (bp.x1, bp.y1), (bp.x2, bp.y2), cor, 2)

            rotulo = "CONFORME" if pessoa.conforme else f"SEM: {', '.join(e.value for e in pessoa.epis_ausentes)}"
            (tw, th), _ = cv2.getTextSize(rotulo, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            cv2.rectangle(frame, (bp.x1, bp.y1 - th - 10), (bp.x1 + tw + 10, bp.y1), cor, -1)
            cv2.putText(frame, rotulo, (bp.x1 + 5, bp.y1 - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)

            for epi_d in pessoa.epis_detectados:
                b = epi_d.bbox
                cv2.rectangle(frame, (b.x1, b.y1), (b.x2, b.y2), _COR_EPI, 1)
                texto = f"{epi_d.classe_nome} {epi_d.confianca * 100:.0f}%"
                cv2.putText(frame, texto, (b.x1, max(b.y1 - 4, 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, _COR_EPI, 1, cv2.LINE_AA)

        return frame
