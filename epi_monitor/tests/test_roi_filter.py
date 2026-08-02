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
