import time
import numpy as np
import pytest
from detection.epi_checker import EPIChecker
from models.detection import Detection, BoundingBox
from models.enums import TipoEPI


def test_debounce_infracao_temporal_30_segundos():
    """Testa a persistência temporal (debounce) de 30 segundos baseada em timestamp."""
    # Configura para 30 segundos
    checker = EPIChecker(epis_obrigatorios=[TipoEPI.CAPACETE], min_segundos_infracao=30.0)

    det_pessoa = Detection(
        classe_id=0,
        classe_nome="pessoa",
        confianca=0.9,
        bbox=BoundingBox(0, 0, 100, 100),
        track_id=10
    )
    fake_frame = np.zeros((200, 200, 3), dtype=np.uint8)

    # Frame 1: Sem capacete no tempo t0 -> não confirma infração ainda
    t0 = time.time()
    res1 = checker.analisar(1, fake_frame, [det_pessoa])
    assert res1.pessoas[0].conforme is True
    assert res1.possui_infracao is False

    # Simula 15 segundos decorridos -> ainda não deve confirmar (15s < 30s)
    checker._primeiro_timestamp_infracao[10] = t0 - 15.0
    res2 = checker.analisar(1, fake_frame, [det_pessoa])
    assert res2.pessoas[0].conforme is True

    # Simula 31 segundos decorridos -> AGORA deve confirmar a infração! (31s >= 30s)
    checker._primeiro_timestamp_infracao[10] = t0 - 31.0
    res3 = checker.analisar(1, fake_frame, [det_pessoa])
    assert res3.pessoas[0].conforme is False
    assert res3.possui_infracao is True
    assert TipoEPI.CAPACETE in res3.pessoas[0].epis_ausentes


def test_reset_debounce_quando_conforme():
    """Testa se a contagem do debounce em segundos é zerada caso a pessoa reapareça conforme."""
    checker = EPIChecker(epis_obrigatorios=[TipoEPI.CAPACETE], min_segundos_infracao=30.0)

    det_pessoa = Detection(
        classe_id=0,
        classe_nome="pessoa",
        confianca=0.9,
        bbox=BoundingBox(0, 0, 100, 100),
        track_id=10
    )
    det_capacete = Detection(
        classe_id=1,
        classe_nome="capacete",
        confianca=0.95,
        bbox=BoundingBox(10, 10, 40, 40)
    )
    fake_frame = np.zeros((200, 200, 3), dtype=np.uint8)

    # Inicia infração
    checker.analisar(1, fake_frame, [det_pessoa])
    assert 10 in checker._primeiro_timestamp_infracao

    # Reaparece com capacete! Deve remover o track do mapa de tempo
    res_ok = checker.analisar(1, fake_frame, [det_pessoa, det_capacete])
    assert res_ok.pessoas[0].conforme is True
    assert 10 not in checker._primeiro_timestamp_infracao
