"""
models/detection.py
--------------------
Estruturas de dados (DTOs) que trafegam entre a camada de detecção,
os serviços de câmera/alerta e a UI. Não têm relação direta com o ORM
(database/models.py) — são objetos de domínio "em memória", leves e
rápidos de criar a cada frame processado.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from models.enums import TipoEPI


@dataclass
class BoundingBox:
    """Caixa delimitadora de uma detecção, em coordenadas de pixel."""
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1


@dataclass
class Detection:
    """Uma única detecção retornada pelo YOLO para um frame."""
    classe_id: int
    classe_nome: str
    confianca: float
    bbox: BoundingBox
    # id de rastreamento (tracking), se o tracker estiver habilitado
    track_id: Optional[int] = None


@dataclass
class PessoaAnalisada:
    """
    Representa UMA pessoa detectada no frame, com os EPIs identificados
    associados a ela (por proximidade espacial da bbox da pessoa).
    """
    bbox_pessoa: BoundingBox
    epis_detectados: List[Detection] = field(default_factory=list)
    epis_ausentes: List[TipoEPI] = field(default_factory=list)
    conforme: bool = True
    track_id: Optional[int] = None

    @property
    def confianca_media(self) -> float:
        if not self.epis_detectados:
            return 0.0
        return sum(d.confianca for d in self.epis_detectados) / len(self.epis_detectados)


@dataclass
class ResultadoAnalise:
    """
    Resultado completo da análise de UM frame de UMA câmera: todas as
    pessoas encontradas, se houve infração, e o frame anotado (com caixas
    desenhadas) pronto para exibição na UI.
    """
    camera_id: int
    timestamp: datetime.datetime
    frame_anotado: np.ndarray
    pessoas: List[PessoaAnalisada] = field(default_factory=list)

    @property
    def possui_infracao(self) -> bool:
        return any(not p.conforme for p in self.pessoas)

    @property
    def todas_deteccoes(self) -> List[Detection]:
        result = []
        for p in self.pessoas:
            result.extend(p.epis_detectados)
        return result
