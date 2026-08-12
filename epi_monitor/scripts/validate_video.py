"""
scripts/validate_video.py
-------------------------
Validação headless (sem GUI) do pipeline de detecção de EPIs sobre um
arquivo de vídeo. Útil para conferir se o modelo carregado está de fato
detectando pessoas/EPIs e se o EPIChecker marca infrações.

Uso:
    python scripts/validate_video.py --video /caminho/video.mp4
    python scripts/validate_video.py --video video.mp4 --salvar-frames 5 --saida storage/validation
    python scripts/validate_video.py --video video.mp4 --epis capacete colete

O que ele reporta:
    - Total de frames processados e tempo/fps médio de inferência
    - Contagem de detecções por classe (após remapeamento de nomes)
    - Quantos frames tiveram pessoas CONFORMES vs em INFRAÇÃO
    - Salva frames anotados de amostra para inspeção visual
"""

from __future__ import annotations

import argparse
import collections
import sys
import time
from pathlib import Path

import cv2

# Permite rodar a partir da raiz do pacote: python scripts/validate_video.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from detection.epi_checker import EPIChecker
from detection.yolo_detector import YoloDetector
from models.enums import TipoEPI


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validação headless do detector de EPIs em vídeo.")
    p.add_argument("--video", required=True, help="Caminho do arquivo de vídeo.")
    p.add_argument("--frame-skip", type=int, default=3, help="Processa 1 a cada N frames (default: 3).")
    p.add_argument("--epis", nargs="+", default=["capacete", "colete"],
                   choices=[e.value for e in TipoEPI], help="EPIs obrigatórios.")
    p.add_argument("--salvar-frames", type=int, default=5, help="Qtd. de frames anotados de amostra a salvar.")
    p.add_argument("--saida", default="storage/validation", help="Diretório para frames anotados.")
    p.add_argument("--max-frames", type=int, default=0, help="Limite de frames processados (0 = sem limite).")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"ERRO: não foi possível abrir o vídeo '{args.video}'")
        return 1

    fps_video = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Vídeo: {args.video} | {total_frames} frames @ {fps_video:.1f} fps "
          f"({total_frames / fps_video:.1f}s)")

    detector = YoloDetector.get_instance()
    epis_obrigatorios = [TipoEPI(e) for e in args.epis]
    # min_segundos_infracao=0: sem tracking em arquivo, confirmamos na hora
    # para avaliar a qualidade da detecção frame a frame.
    checker = EPIChecker(epis_obrigatorios=epis_obrigatorios, min_segundos_infracao=0.0)

    dir_saida = Path(args.saida)
    dir_saida.mkdir(parents=True, exist_ok=True)

    contagem_classes: collections.Counter[str] = collections.Counter()
    frames_processados = 0
    frames_com_pessoas = 0
    frames_com_infracao = 0
    frames_conformes = 0
    amostras_salvas = 0
    tempos_inferencia: list[float] = []

    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % args.frame_skip != 0:
            idx += 1
            continue

        t0 = time.perf_counter()
        deteccoes = detector.predict(frame)
        tempos_inferencia.append(time.perf_counter() - t0)

        for d in deteccoes:
            contagem_classes[d.classe_nome] += 1

        resultado = checker.analisar(camera_id=0, frame=frame, deteccoes=deteccoes)
        frames_processados += 1

        if resultado.pessoas:
            frames_com_pessoas += 1
            if any(not p.conforme for p in resultado.pessoas):
                frames_com_infracao += 1
            elif all(p.conforme for p in resultado.pessoas):
                frames_conformes += 1

        if amostras_salvas < args.salvar_frames and resultado.pessoas:
            # Espaça as amostras ao longo do vídeo
            if frames_processados % max(1, (total_frames // args.frame_skip) // max(args.salvar_frames, 1)) == 0:
                cv2.imwrite(str(dir_saida / f"frame_{idx:06d}.jpg"), resultado.frame_anotado)
                amostras_salvas += 1

        if args.max_frames and frames_processados >= args.max_frames:
            break
        idx += 1

    cap.release()

    tempo_medio = (sum(tempos_inferencia) / len(tempos_inferencia)) if tempos_inferencia else 0.0

    print("\n===== RELATÓRIO DE VALIDAÇÃO =====")
    print(f"Frames processados:        {frames_processados}")
    print(f"Inferência média por frame: {tempo_medio * 1000:.0f} ms ({1 / tempo_medio:.1f} fps)" if tempo_medio else "")
    print(f"Frames com pessoas:        {frames_com_pessoas}")
    print(f"Frames CONFORMES:          {frames_conformes}")
    print(f"Frames com INFRAÇÃO:       {frames_com_infracao}")
    print("\nDetecções por classe (nome interno):")
    for classe, qtd in contagem_classes.most_common():
        print(f"  {classe:<20} {qtd}")
    if not contagem_classes:
        print("  (nenhuma detecção — verifique se o modelo EPI está carregado)")
    print(f"\nFrames anotados salvos em: {dir_saida.resolve()} ({amostras_salvas} amostras)")

    # Heurística de sanidade: se nunca detectou 'pessoa', o modelo carregado
    # provavelmente não é o de EPI (ou o remapeamento falhou).
    if contagem_classes.get("pessoa", 0) == 0:
        print("\nALERTA: nenhuma pessoa detectada. Confira YOLO_MODEL_PATH e o remapeamento de classes.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
