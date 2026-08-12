"""
services/event_service.py
----------------------------
Persiste os eventos gerados pela análise de detecção no banco de dados
(tabela `eventos`) e fornece consultas para a tela de Histórico/Dashboard.
"""

from __future__ import annotations

import json
import datetime
import logging
from typing import List, Optional, Sequence

from sqlalchemy import select, func

from database.connection import get_session
from database.models import Evento, Camera
from models.detection import ResultadoAnalise, PessoaAnalisada
from models.enums import TipoEvento

logger = logging.getLogger(__name__)


class EventService:

    @staticmethod
    def registrar_evento(
        camera_id: int,
        pessoa: PessoaAnalisada,
        snapshot_path: Optional[str] = None,
        video_clip_path: Optional[str] = None,
    ) -> Evento:
        """Cria e persiste um registro de evento (infração ou conformidade)."""
        tipo = TipoEvento.INFRACAO if not pessoa.conforme else TipoEvento.CONFORMIDADE
        epis_ausentes_json = json.dumps([e.value for e in pessoa.epis_ausentes])

        with get_session() as session:
            evento = Evento(
                camera_id=camera_id,
                tipo_evento=tipo,
                epis_ausentes_json=epis_ausentes_json,
                confianca_media=pessoa.confianca_media,
                caminho_snapshot=snapshot_path,
                caminho_video_clip=video_clip_path,
            )
            session.add(evento)
            session.commit()
            session.refresh(evento)
            session.expunge(evento)
            return evento

    @staticmethod
    def registrar_evento_sistema(camera_id: Optional[int], tipo: TipoEvento, observacoes: str) -> Evento:
        """Registra eventos de sistema (câmera caiu/voltou, etc.)."""
        with get_session() as session:
            evento = Evento(camera_id=camera_id, tipo_evento=tipo, observacoes=observacoes)
            session.add(evento)
            session.commit()
            session.refresh(evento)
            session.expunge(evento)
            return evento

    @staticmethod
    def atualizar_clip_evento(evento_id: int, caminho_clip: str) -> None:
        """
        Atualiza o caminho do vídeo clipe em um evento existente.
        Thread-safe: usa sessão própria (chamável de threads de background).
        """
        with get_session() as session:
            evento = session.get(Evento, evento_id)
            if evento:
                evento.caminho_video_clip = caminho_clip
                session.commit()
            else:
                logger.warning(f"Evento {evento_id} não encontrado para atualizar clip.")

    @staticmethod
    def listar_eventos(
        camera_id: Optional[int] = None,
        tipo: Optional[TipoEvento] = None,
        data_inicio: Optional[datetime.datetime] = None,
        data_fim: Optional[datetime.datetime] = None,
        limite: int = 200,
    ) -> Sequence[Evento]:
        """Consulta paginada/filtrada de eventos para a tela de Histórico."""
        with get_session() as session:
            stmt = select(Evento).order_by(Evento.data_hora.desc()).limit(limite)
            if camera_id is not None:
                stmt = stmt.where(Evento.camera_id == camera_id)
            if tipo is not None:
                stmt = stmt.where(Evento.tipo_evento == tipo)
            if data_inicio is not None:
                stmt = stmt.where(Evento.data_hora >= data_inicio)
            if data_fim is not None:
                stmt = stmt.where(Evento.data_hora <= data_fim)

            eventos = list(session.scalars(stmt).all())
            for e in eventos:
                session.expunge(e)
            return eventos

    @staticmethod
    def estatisticas_dashboard(dias: int = 7) -> dict:
        """
        Agrega estatísticas para o dashboard:
            - total de infrações no período
            - total de conformidades
            - taxa de conformidade (%)
            - infrações por câmera (ranking)
            - infrações por dia (série temporal)
        """
        desde = datetime.datetime.now() - datetime.timedelta(days=dias)

        with get_session() as session:
            total_infracoes = session.scalar(
                select(func.count(Evento.id)).where(
                    Evento.tipo_evento == TipoEvento.INFRACAO, Evento.data_hora >= desde
                )
            ) or 0

            total_conformidade = session.scalar(
                select(func.count(Evento.id)).where(
                    Evento.tipo_evento == TipoEvento.CONFORMIDADE, Evento.data_hora >= desde
                )
            ) or 0

            total_geral = total_infracoes + total_conformidade
            taxa_conformidade = (total_conformidade / total_geral * 100) if total_geral else 100.0

            ranking_query = (
                select(Camera.nome, func.count(Evento.id).label("qtd"))
                .join(Evento, Evento.camera_id == Camera.id)
                .where(Evento.tipo_evento == TipoEvento.INFRACAO, Evento.data_hora >= desde)
                .group_by(Camera.nome)
                .order_by(func.count(Evento.id).desc())
                .limit(10)
            )
            ranking = [{"camera": nome, "infracoes": qtd} for nome, qtd in session.execute(ranking_query).all()]

            serie_query = (
                select(func.date(Evento.data_hora).label("dia"), func.count(Evento.id).label("qtd"))
                .where(Evento.tipo_evento == TipoEvento.INFRACAO, Evento.data_hora >= desde)
                .group_by(func.date(Evento.data_hora))
                .order_by(func.date(Evento.data_hora))
            )
            serie_temporal = [{"dia": str(dia), "infracoes": qtd} for dia, qtd in session.execute(serie_query).all()]

            local_query = (
                select(
                    func.coalesce(Camera.localizacao, "Sem local").label("local"),
                    func.count(Evento.id).label("qtd"),
                )
                .join(Evento, Evento.camera_id == Camera.id)
                .where(Evento.tipo_evento == TipoEvento.INFRACAO, Evento.data_hora >= desde)
                .group_by(func.coalesce(Camera.localizacao, "Sem local"))
                .order_by(func.count(Evento.id).desc())
            )
            infracoes_por_local = [
                {"local": local, "infracoes": qtd}
                for local, qtd in session.execute(local_query).all()
            ]

            return {
                "total_infracoes": total_infracoes,
                "total_conformidade": total_conformidade,
                "taxa_conformidade": round(taxa_conformidade, 1),
                "ranking_cameras": ranking,
                "serie_temporal": serie_temporal,
                "infracoes_por_local": infracoes_por_local,
            }
