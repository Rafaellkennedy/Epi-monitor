"""
services/onvif_service.py
---------------------------
Integração com o protocolo ONVIF, usado para:
    1. DESCOBRIR câmeras compatíveis na rede local (WS-Discovery).
    2. Obter automaticamente a URI RTSP correta de uma câmera a partir
       de host/porta/usuário/senha (evita o usuário ter que descobrir
       manualmente a URL RTSP, que varia por fabricante).
    3. (Futuro) Comandos PTZ - pan/tilt/zoom.

Depende da biblioteca `onvif-zeep` (pacote `onvif2-zeep` ou `onvif-zeep-async`).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CameraDescoberta:
    """Resultado de uma câmera encontrada via WS-Discovery na rede."""
    endereco_ip: str
    porta: int
    tipos: List[str]
    xaddrs: List[str]


class OnvifService:
    """Encapsula operações ONVIF. Import da lib é feito de forma lazy
    (dentro dos métodos) para não travar o startup da aplicação caso a
    lib ou suas dependências (zeep) não estejam disponíveis/instaladas."""

    @staticmethod
    def descobrir_cameras(timeout: int = 5) -> List[CameraDescoberta]:
        """
        Varre a rede local em busca de dispositivos ONVIF (WS-Discovery).
        Retorna lista de câmeras encontradas para o usuário escolher no
        cadastro, em vez de digitar IP manualmente.
        """
        try:
            from wsdiscovery.discovery import ThreadedWSDiscovery as WSDiscovery
        except ImportError:
            logger.error("Biblioteca 'WSDiscovery' não instalada. Execute: pip install WSDiscovery")
            return []

        wsd = WSDiscovery()
        encontrados: List[CameraDescoberta] = []
        try:
            wsd.start()
            services = wsd.searchServices(timeout=timeout)
            for svc in services:
                xaddrs = svc.getXAddrs()
                if not xaddrs:
                    continue
                # Extrai host/porta do primeiro XAddr (formato http://IP:PORT/onvif/device_service)
                url = xaddrs[0]
                host_porta = url.split("//")[-1].split("/")[0]
                host = host_porta.split(":")[0]
                porta = int(host_porta.split(":")[1]) if ":" in host_porta else 80
                encontrados.append(CameraDescoberta(
                    endereco_ip=host, porta=porta,
                    tipos=[str(t) for t in svc.getTypes()],
                    xaddrs=xaddrs,
                ))
        finally:
            wsd.stop()

        return encontrados

    @staticmethod
    def obter_rtsp_uri(host: str, porta: int, usuario: str, senha: str) -> Optional[str]:
        """
        Conecta na câmera via ONVIF e solicita o perfil de mídia para
        obter a URI RTSP real (com token de stream correto do fabricante).
        """
        try:
            from onvif import ONVIFCamera
        except ImportError:
            logger.error("Biblioteca 'onvif-zeep' não instalada. Execute: pip install onvif-zeep")
            return None

        try:
            cam = ONVIFCamera(host, porta, usuario, senha)
            media_service = cam.create_media_service()
            profiles = media_service.GetProfiles()

            if not profiles:
                logger.error(f"Nenhum perfil de mídia encontrado na câmera {host}.")
                return None

            token = profiles[0].token
            stream_setup = {
                "Stream": "RTP-Unicast",
                "Transport": {"Protocol": "RTSP"},
            }
            uri_response = media_service.GetStreamUri({
                "StreamSetup": stream_setup,
                "ProfileToken": token,
            })

            rtsp_url = uri_response.Uri
            # Injeta usuário/senha na URL (padrão RTSP com autenticação embutida)
            if usuario and "@" not in rtsp_url:
                protocolo, resto = rtsp_url.split("://", 1)
                rtsp_url = f"{protocolo}://{usuario}:{senha}@{resto}"

            return rtsp_url
        except Exception as e:
            logger.error(f"Erro ao obter URI RTSP via ONVIF de {host}: {e}")
            return None
