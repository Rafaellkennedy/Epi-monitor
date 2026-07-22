"""
ui/widgets/camera_widget.py
------------------------------
Widget reutilizável que exibe o vídeo de UMA câmera dentro do grid de
monitoramento, junto com nome, status de conexão e indicador de infração.

A conversão de frame (numpy array BGR do OpenCV) para QPixmap acontece
aqui, isolando essa responsabilidade de renderização da lógica de negócio.
"""

from __future__ import annotations

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
    StatusCamera.ONLINE: "● Online",
    StatusCamera.OFFLINE: "● Offline",
    StatusCamera.RECONECTANDO: "● Reconectando...",
    StatusCamera.ERRO: "● Erro",
    StatusCamera.DESATIVADA: "● Desativada",
}


class CameraWidget(QFrame):
    """Um "card" de câmera individual: vídeo + cabeçalho com nome/status."""

    def __init__(self, camera_id: int, nome: str) -> None:
        super().__init__()
        self.camera_id = camera_id
        self.setObjectName("card")
        self._montar_ui(nome)

    def _montar_ui(self, nome: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        header = QHBoxLayout()
        self.label_nome = QLabel(nome)
        self.label_nome.setStyleSheet("font-weight: 600; font-size: 12px;")
        self.label_status = QLabel(_STATUS_LABEL[StatusCamera.OFFLINE])
        self.label_status.setObjectName(_STATUS_OBJ_NAME[StatusCamera.OFFLINE])
        header.addWidget(self.label_nome)
        header.addStretch()
        header.addWidget(self.label_status)
        layout.addLayout(header)

        self.label_video = QLabel("Aguardando conexão...")
        self.label_video.setAlignment(Qt.AlignCenter)
        self.label_video.setMinimumSize(320, 180)
        self.label_video.setStyleSheet("background-color: #05060a; border-radius: 6px; color: #4b4f5a;")
        self.label_video.setScaledContents(False)
        layout.addWidget(self.label_video)

    def atualizar_frame(self, frame_bgr: np.ndarray) -> None:
        """Recebe um frame OpenCV (BGR) e atualiza a exibição."""
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = frame_rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg).scaled(
            self.label_video.width(), self.label_video.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.label_video.setPixmap(pixmap)

    def atualizar_status(self, status: StatusCamera) -> None:
        self.label_status.setText(_STATUS_LABEL.get(status, status.value))
        self.label_status.setObjectName(_STATUS_OBJ_NAME.get(status, "statusOffline"))
        # Força reavaliação do QSS após troca de objectName
        self.label_status.style().unpolish(self.label_status)
        self.label_status.style().polish(self.label_status)
