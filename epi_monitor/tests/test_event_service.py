"""
Testes de EventService: atualizar_clip_evento e infracoes_por_local.
"""

import json
import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.event_service import EventService
from models.enums import TipoEPI, TipoEvento
from models.detection import Detection, BoundingBox, PessoaAnalisada
from database.models import Base, Camera, Evento

# Cria engine SQLite em memória para testes isolados
test_engine = create_engine("sqlite:///:memory:", echo=False)
TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


@pytest.fixture
def db_session():
    """Configura o banco SQLite em memória, cria schema e substitui get_session."""
    Base.metadata.create_all(bind=test_engine)

    from contextlib import contextmanager

    @contextmanager
    def override_get_session():
        session = TestingSessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    with patch("services.event_service.get_session", side_effect=override_get_session):
        yield

    Base.metadata.drop_all(bind=test_engine)


def _criar_camera(session, nome, localizacao):
    camera = Camera(nome=nome, localizacao=localizacao, url_rtsp=f"rtsp://fake/{nome}")
    session.add(camera)
    session.commit()
    session.refresh(camera)
    return camera


def _criar_pessoa_infracao(epis_ausentes):
    """Cria PessoaAnalisada com infração (não conforme)."""
    pessoa = PessoaAnalisada(
        bbox_pessoa=BoundingBox(0, 0, 100, 100),
        epis_ausentes=epis_ausentes,
        conforme=False,
        track_id=1,
    )
    pessoa.epis_detectados = [
        Detection(
            classe_id=0,
            classe_nome="pessoa",
            confianca=0.9,
            bbox=BoundingBox(0, 0, 100, 100),
            track_id=1,
        )
    ]
    return pessoa


def test_atualizar_clip_evento(db_session):
    """Testa se atualizar_clip_evento persiste o caminho do clipe no evento."""
    with TestingSessionLocal() as session:
        camera = _criar_camera(session, "Cam Teste", "Área A")
        camera_id = camera.id
        session.expunge(camera)

    pessoa = _criar_pessoa_infracao([TipoEPI.CAPACETE])

    # Registra evento via serviço (usando o mock de get_session)
    evento = EventService.registrar_evento(
        camera_id=camera_id,
        pessoa=pessoa,
        snapshot_path="/fake/snapshot.jpg",
    )
    assert evento.id is not None
    assert evento.caminho_video_clip is None

    # Atualiza o clip
    EventService.atualizar_clip_evento(evento.id, "/fake/clip.mp4")

    # Verifica se foi persistido
    with TestingSessionLocal() as session:
        atualizado = session.get(Evento, evento.id)
        assert atualizado is not None
        assert atualizado.caminho_video_clip == "/fake/clip.mp4"


def test_atualizar_clip_evento_nao_encontrado(db_session):
    """atualizar_clip_evento não deve lançar exceção para evento inexistente."""
    # Deve rodar sem erro (apenas log warning)
    EventService.atualizar_clip_evento(999999, "/fake/clip.mp4")


def test_infracoes_por_local(db_session):
    """Testa a agregação infracoes_por_local nas estatísticas."""
    with TestingSessionLocal() as session:
        cam_a = _criar_camera(session, "Cam A", "Portaria")
        cam_b = _criar_camera(session, "Cam B", "Galpão")
        cam_c = _criar_camera(session, "Cam C", "Portaria")
        cam_d = _criar_camera(session, "Cam D", None)  # sem localização
        # Guarda os IDs antes do fechamento da sessão
        id_a, id_b, id_c, id_d = cam_a.id, cam_b.id, cam_c.id, cam_d.id

    pessoa = _criar_pessoa_infracao([TipoEPI.CAPACETE])

    # Registra múltiplos eventos de infração usando os IDs guardados
    EventService.registrar_evento(camera_id=id_a, pessoa=pessoa)
    EventService.registrar_evento(camera_id=id_a, pessoa=pessoa)
    EventService.registrar_evento(camera_id=id_a, pessoa=pessoa)  # 3 em Portaria via Cam A
    EventService.registrar_evento(camera_id=id_b, pessoa=pessoa)  # 1 em Galpão
    EventService.registrar_evento(camera_id=id_c, pessoa=pessoa)  # 1 em Portaria via Cam C
    EventService.registrar_evento(camera_id=id_d, pessoa=pessoa)  # 1 sem local

    stats = EventService.estatisticas_dashboard(dias=365)

    assert "infracoes_por_local" in stats
    infracoes = stats["infracoes_por_local"]

    # Deve ser ordenado desc por quantidade de infrações
    # Portaria: 4 (Cam A:3 + Cam C:1), Galpão: 1, Sem local: 1
    assert len(infracoes) == 3
    assert infracoes[0]["local"] == "Portaria"
    assert infracoes[0]["infracoes"] == 4
    assert infracoes[1]["local"] in ("Galpão", "Sem local")
    assert infracoes[1]["infracoes"] == 1
    assert infracoes[2]["local"] in ("Galpão", "Sem local")
    assert infracoes[2]["infracoes"] == 1


def test_infracoes_por_local_sem_eventos(db_session):
    """infracoes_por_local deve retornar lista vazia quando não há eventos."""
    stats = EventService.estatisticas_dashboard(dias=1)
    assert "infracoes_por_local" in stats
    assert stats["infracoes_por_local"] == []