"""
ui/widgets/camera_widget.py
------------------------------
Widget reutilizável que exibe o vídeo de UMA câmera dentro do grid de
monitoramento, junto com nome, localização, tipo de fonte, status de
conexão e indicador de infração.

A conversão de frame (numpy array BGR do OpenCV) para QPixmap acontece
aqui, isolando essa responsabilidade de renderização da lógica de negócio.
"""

from __future__ import annotations

import time
import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame

from models.enums import StatusCamera

_STATUS_OBJ_NAME = {
    StatusCamera.ONLINE: "statusOnline",
    StatusCamera.OFFLINE: "statusOffline",
    StatusCamera.RECONECTANDO: "statusReconnecting",
    StatusCamera.ERRO: "statusOffline",
    StatusCamera.DESATIVADA: "statusOffline",
}

_STATUS_LABEL = {
    StatusCamera.ONLINE: "\u25CF Online",
    StatusCamera.OFFLINE: "\u25CF Offline",
    StatusCamera.RECONECTANDO: "\u25CF Reconectando...",
    StatusCamera.ERRO: "\u25CF Erro",
    StatusCamera.DESATIVADA: "\u25CF Desativada",
}

_TIPO_FONTE_LABEL = {
    "rtsp": "IP (RTSP)",
    "arquivo": "Arquivo",
    "webcam": "Webcam",
}


class CameraWidget(QFrame):
    """Um \"card\" de câmera individual: vídeo + cabeçalho com nome/localização/status."""

    def __init__(
        self,
        camera_id: int,
        nome: str,
        localizacao: str = "",
        tipo_fonte: str = "",
        max_ui_fps: int = 5,
    ) -> None:
        super().__init__()
        self.camera_id = camera_id
        self.max_ui_fps = max_ui_fps
        self._min_interval = 1.0 / max(max_ui_fps, 1)
        self._ultimo_render_ts = 0.0
        self.setObjectName("card")
        self._montar_ui(nome, localizacao, tipo_fonte)

    def _montar_ui(self, nome: str, localizacao: str, tipo_fonte: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # --- Cabeçalho com nome, localização e status ---
        header = QVBoxLayout()
        header.setSpacing(2)

        linha1 = QHBoxLayout()
        self.label_nome = QLabel(nome)
        self.label_nome.setStyleSheet("font-weight: 700; font-size: 13px;")
        self.label_status = QLabel(_STATUS_LABEL[StatusCamera.OFFLINE])
        self.label_status.setObjectName(_STATUS_OBJ_NAME[StatusCamera.OFFLINE])
        linha1.addWidget(self.label_nome)
        linha1.addStretch()
        linha1.addWidget(self.label_status)
        header.addLayout(linha1)

        # Linha opcional: localização + selo de tipo de fonte
        if localizacao or tipo_fonte:
            linha2 = QHBoxLayout()
            if localizacao:
                lbl_loc = QLabel(localizacao)
                lbl_loc.setStyleSheet("font-size: 11px; color: #9498a3;")
                linha2.addWidget(lbl_loc)
            if tipo_fonte:
                selo = QLabel(_TIPO_FONTE_LABEL.get(tipo_fonte, tipo_fonte))
                selo.setStyleSheet(
                    "font-size: 10px; font-weight: 600; background-color: #23262f; "
                    "color: #b5b8c2; border-radius: 4px; padding: 2px 6px;"
                )
                selo.setObjectName("sourceBadge")
                if localizacao:
                    linha2.addWidget(selo)
                else:
                    linha2.addStretch()
                    linha2.addWidget(selo)
            linha2.addStretch()
            header.addLayout(linha2)

        layout.addLayout(header)

        # --- Área de vídeo ---
        self.label_video = QLabel("Aguardando conex\u00e3o...")
        self.label_video.setAlignment(Qt.AlignCenter)
        self.label_video.setMinimumSize(280, 160)
        self.label_video.setStyleSheet(
            "background-color: #05060a; border-radius: 6px; color: #4b4f5a;"
        )
        self.label_video.setScaledContents(False)
        layout.addWidget(self.label_video)

    def atualizar_frame(self, frame_bgr: np.ndarray) -> None:
        """Recebe um frame OpenCV (BGR) e atualiza a exibi\u00e7\u00e3o respeitando o limite de FPS da UI."""
        agora = time.time()
        if (agora - self._ultimo_render_ts) < self._min_interval:
            return

        self._ultimo_render_ts = agora

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = frame_rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg).scaled(
            self.label_video.width(),
            self.label_video.height(),
            Qt.KeepAspectRatio,
            Qt.FastTransformation,
        )
        self.label_video.setPixmap(pixmap)

    def atualizar_status(self, status: StatusCamera) -> None:
        self.label_status.setText(_STATUS_LABEL.get(status, status.value))
        self.label_status.setObjectName(_STATUS_OBJ_NAME.get(status, "statusOffline"))
        self.label_status.style().unpolish(self.label_status)
        self.label_status.style().polish(self.label_status)