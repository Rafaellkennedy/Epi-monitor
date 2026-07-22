"""
installer/auto_updater.py
----------------------------
Atualizador automático simples baseado em "verificação de versão remota".

Funcionamento:
    1. O executável publicado inclui um arquivo `version.txt` com a versão
       atual (ex.: "1.0.0").
    2. Este script consulta uma URL configurada (ex.: um JSON hospedado no
       servidor da empresa ou em um bucket S3/GitHub Releases) contendo a
       versão mais recente disponível e a URL do instalador.
    3. Se a versão remota for mais nova, baixa o novo instalador e o
       executa, substituindo a versão atual (o instalador NSIS/Inno Setup
       gerado deve suportar update "silencioso" sobre instalação existente).

Este módulo é INTENCIONALMENTE simples (infraestrutura mínima viável).
Para um pipeline de atualização robusto em produção, considere usar
frameworks dedicados como `PyUpdater` ou publicar releases via GitHub e
usar a API de Releases para checagem/download automatizados.

Uso (executado periodicamente pela aplicação principal, ou manualmente
pelo administrador via menu "Verificar atualizações"):

    from installer.auto_updater import verificar_atualizacao
    verificar_atualizacao()
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

import requests  # necessário: pip install requests

logger = logging.getLogger(__name__)

VERSION_FILE = Path(__file__).resolve().parent.parent / "version.txt"

# URL do manifesto de versão. Deve retornar um JSON como:
# {"versao": "1.1.0", "url_instalador": "https://.../EPIMonitor_Setup_1.1.0.exe",
#  "notas": "Correções de bugs e melhoria de desempenho."}
UPDATE_MANIFEST_URL = "https://SEU-SERVIDOR.com/epi_monitor/latest.json"


def _versao_atual() -> str:
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    return "0.0.0"


def _versao_maior(v_remota: str, v_local: str) -> bool:
    """Compara versões no formato semântico simples MAJOR.MINOR.PATCH."""
    def _parse(v: str) -> tuple[int, ...]:
        return tuple(int(p) for p in v.split(".") if p.isdigit())
    return _parse(v_remota) > _parse(v_local)


def verificar_atualizacao(perguntar_usuario: bool = True) -> None:
    """Verifica se há atualização disponível e, opcionalmente, aplica."""
    try:
        resposta = requests.get(UPDATE_MANIFEST_URL, timeout=10)
        resposta.raise_for_status()
        manifesto = resposta.json()
    except Exception as e:
        logger.warning(f"Não foi possível verificar atualizações: {e}")
        return

    versao_remota = manifesto.get("versao", "0.0.0")
    versao_local = _versao_atual()

    if not _versao_maior(versao_remota, versao_local):
        logger.info(f"EPI Monitor já está atualizado (versão {versao_local}).")
        return

    logger.info(f"Nova versão disponível: {versao_remota} (atual: {versao_local}).")

    if perguntar_usuario:
        try:
            from PySide6.QtWidgets import QMessageBox
            resp = QMessageBox.question(
                None, "Atualização disponível",
                f"Uma nova versão ({versao_remota}) está disponível.\n\n"
                f"{manifesto.get('notas', '')}\n\nDeseja atualizar agora?"
            )
            if resp != QMessageBox.Yes:
                return
        except Exception:
            pass  # ambiente sem Qt disponível (ex.: chamada via CLI)

    _baixar_e_instalar(manifesto["url_instalador"])


def _baixar_e_instalar(url_instalador: str) -> None:
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            destino = Path(tmp_dir) / "EPIMonitor_Setup.exe"
            logger.info(f"Baixando atualização de {url_instalador}...")

            with requests.get(url_instalador, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(destino, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

            logger.info("Download concluído. Iniciando instalador...")
            # /S = instalação silenciosa (padrão NSIS). Ajustar conforme o
            # instalador gerado (Inno Setup usa /VERYSILENT, por exemplo).
            subprocess.Popen([str(destino), "/S"])
            sys.exit(0)  # encerra a aplicação atual para o instalador substituir os arquivos
    except Exception as e:
        logger.error(f"Falha ao baixar/aplicar atualização: {e}")
