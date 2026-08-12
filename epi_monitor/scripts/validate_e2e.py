"""
scripts/validate_e2e.py
-----------------------
Validação end-to-end do pipeline completo (sem GUI):

    arquivo de vídeo -> CameraStream -> YoloDetector -> EPIChecker
        -> snapshot JPEG + clipe MP4 + evento no banco (com caminho_video_clip)

Pré-requisitos:
    - PostgreSQL acessível conforme .env (ex.: docker compose up -d db)
    - .env com YOLO_MODEL_PATH apontando para um modelo EPI real

Uso:
    python scripts/validate_e2e.py --video /caminho/video.mp4 [--duracao 35]

Ao final, imprime os eventos criados NESTA execução e verifica se:
    - o snapshot existe em disco
    - o caminho_video_clip foi persistido no banco (callback assíncrono)
    - o arquivo de clipe existe em disco
Exit code 0 = tudo validado; 1 = falha.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.connection import get_session, init_db
from database.models import Evento
from models.enums import TipoEPI
from services.alert_service import AlertService
from services.camera_repository import CameraRepository
from services.camera_service import CameraManager
from services.detection_pipeline import DetectionPipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Validação end-to-end do pipeline de detecção.")
    parser.add_argument("--video", required=True, help="Caminho do vídeo usado como 'câmera'.")
    parser.add_argument("--duracao", type=int, default=35, help="Segundos de monitoramento (default: 35).")
    parser.add_argument("--espera-clipe", type=int, default=20,
                        help="Segundos de espera extra p/ finalização do clipe (default: 20).")
    args = parser.parse_args()

    if not Path(args.video).exists():
        print(f"ERRO: vídeo não encontrado: {args.video}")
        return 1

    init_db()

    camera = CameraRepository.criar(
        nome="validacao-e2e",
        url_rtsp=args.video,
        localizacao="Validação E2E",
        epis_obrigatorios=[TipoEPI.CAPACETE, TipoEPI.COLETE],
        fps_alvo=10,
    )
    print(f"Câmera de validação criada: id={camera.id}")

    with get_session() as session:
        ultimo_id_antes = session.query(Evento.id).order_by(Evento.id.desc()).first()
        id_corte = ultimo_id_antes[0] if ultimo_id_antes else 0

    manager = CameraManager()
    alertas = AlertService()
    pipeline = DetectionPipeline(camera_manager=manager, alert_service=alertas)

    inicio = time.time()
    try:
        pipeline.iniciar_camera(camera)
        pipeline.start_loop_processamento()
        print(f"Pipeline rodando por {args.duracao}s...")
        while time.time() - inicio < args.duracao:
            time.sleep(1)
    finally:
        pipeline.parar_tudo()

    print(f"Aguardando finalização do clipe ({args.espera_clipe}s)...")
    time.sleep(args.espera_clipe)

    falhas: list[str] = []
    with get_session() as session:
        eventos = (
            session.query(Evento)
            .filter(Evento.id > id_corte, Evento.camera_id == camera.id)
            .order_by(Evento.id)
            .all()
        )
        # Expunge para inspecionar fora da sessão
        dados = [
            {
                "id": e.id,
                "tipo": e.tipo_evento.value if hasattr(e.tipo_evento, "value") else str(e.tipo_evento),
                "snapshot": e.caminho_snapshot,
                "clip": e.caminho_video_clip,
            }
            for e in eventos
        ]

    infracoes = [d for d in dados if "infracao" in d["tipo"]]
    print(f"\n===== RESULTADO E2E =====")
    print(f"Eventos novos desta câmera: {len(dados)} (infrações: {len(infracoes)})")
    for d in dados:
        print(f"  evento #{d['id']}: {d['tipo']} | snapshot={d['snapshot']} | clip={d['clip']}")

    if not infracoes:
        falhas.append("Nenhum evento de infração foi registrado.")

    for d in infracoes:
        if not d["snapshot"] or not Path(d["snapshot"]).exists():
            falhas.append(f"Evento #{d['id']}: snapshot ausente em disco ({d['snapshot']}).")
        if not d["clip"]:
            falhas.append(f"Evento #{d['id']}: caminho_video_clip NÃO persistido no banco.")
        elif not Path(d["clip"]).exists():
            falhas.append(f"Evento #{d['id']}: clipe não existe em disco ({d['clip']}.")

    # Desativa a câmera de validação (mantém os eventos para inspeção na UI)
    CameraRepository.atualizar(camera.id, ativa=False)
    print(f"\nCâmera de validação desativada (id={camera.id}). Eventos mantidos para inspeção na UI.")

    if falhas:
        print("\nFALHAS:")
        for f in falhas:
            print(f"  - {f}")
        return 1

    print("\nE2E OK: infração registrada, snapshot e clipe persistidos e vinculados ao evento.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
