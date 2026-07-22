"""
services/camera_repository.py
--------------------------------
Camada de persistência (CRUD) para o cadastro de câmeras e seus EPIs
obrigatórios. Separado de `camera_service.py` propositalmente: aquele
lida com a CAPTURA DE VÍDEO em tempo real (thread), este lida com o
CADASTRO em banco (Clean Architecture: infraestrutura de streaming
≠ persistência de configuração).
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from sqlalchemy import select

from database.connection import get_session
from database.models import Camera, CameraEPI
from models.enums import ProtocoloCamera, StatusCamera, TipoEPI


class CameraRepository:

    @staticmethod
    def criar(
        nome: str,
        url_rtsp: str,
        localizacao: Optional[str] = None,
        protocolo: ProtocoloCamera = ProtocoloCamera.RTSP,
        epis_obrigatorios: Optional[List[TipoEPI]] = None,
        fps_alvo: int = 10,
        onvif_host: Optional[str] = None,
        onvif_port: Optional[int] = None,
        onvif_usuario: Optional[str] = None,
        onvif_senha: Optional[str] = None,
    ) -> Camera:
        with get_session() as session:
            camera = Camera(
                nome=nome,
                localizacao=localizacao,
                protocolo=protocolo,
                url_rtsp=url_rtsp,
                fps_alvo=fps_alvo,
                status=StatusCamera.OFFLINE,
                onvif_host=onvif_host,
                onvif_port=onvif_port,
                onvif_usuario=onvif_usuario,
                onvif_senha=onvif_senha,
            )
            session.add(camera)
            session.flush()  # garante camera.id antes de criar os EPIs associados

            for epi in (epis_obrigatorios or []):
                session.add(CameraEPI(camera_id=camera.id, tipo_epi=epi, obrigatorio=True))

            session.commit()
            session.refresh(camera)
            session.expunge(camera)
            return camera

    @staticmethod
    def atualizar(camera_id: int, **campos) -> Optional[Camera]:
        with get_session() as session:
            camera = session.get(Camera, camera_id)
            if camera is None:
                return None
            for chave, valor in campos.items():
                if hasattr(camera, chave):
                    setattr(camera, chave, valor)
            session.commit()
            session.refresh(camera)
            session.expunge(camera)
            return camera

    @staticmethod
    def atualizar_epis_obrigatorios(camera_id: int, epis: List[TipoEPI]) -> None:
        """Substitui a lista de EPIs obrigatórios da câmera."""
        with get_session() as session:
            session.query(CameraEPI).filter_by(camera_id=camera_id).delete()
            for epi in epis:
                session.add(CameraEPI(camera_id=camera_id, tipo_epi=epi, obrigatorio=True))
            session.commit()

    @staticmethod
    def remover(camera_id: int) -> bool:
        with get_session() as session:
            camera = session.get(Camera, camera_id)
            if camera is None:
                return False
            session.delete(camera)
            session.commit()
            return True

    @staticmethod
    def listar_todas(apenas_ativas: bool = False) -> Sequence[Camera]:
        with get_session() as session:
            stmt = select(Camera)
            if apenas_ativas:
                stmt = stmt.where(Camera.ativa.is_(True))
            cameras = list(session.scalars(stmt).all())
            for c in cameras:
                _ = [e.tipo_epi for e in c.epis_obrigatorios]  # força carregamento antes do expunge
                session.expunge(c)
            return cameras

    @staticmethod
    def buscar_por_id(camera_id: int) -> Optional[Camera]:
        with get_session() as session:
            camera = session.get(Camera, camera_id)
            if camera is None:
                return None
            _ = [e.tipo_epi for e in camera.epis_obrigatorios]
            session.expunge(camera)
            return camera

    @staticmethod
    def epis_obrigatorios_da_camera(camera_id: int) -> List[TipoEPI]:
        with get_session() as session:
            stmt = select(CameraEPI.tipo_epi).where(
                CameraEPI.camera_id == camera_id, CameraEPI.obrigatorio.is_(True)
            )
            return list(session.scalars(stmt).all())

    @staticmethod
    def atualizar_status(camera_id: int, status: StatusCamera) -> None:
        with get_session() as session:
            camera = session.get(Camera, camera_id)
            if camera:
                camera.status = status
                session.commit()
