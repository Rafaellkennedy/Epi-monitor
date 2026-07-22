"""
ui/pages/cameras_page.py
---------------------------
Tela principal de operação: exibe o grid com o vídeo ao vivo de todas as
câmeras cadastradas (com as detecções desenhadas) e permite cadastrar,
editar e remover câmeras, incluindo os EPIs obrigatórios de cada uma.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QDialog, QFormLayout, QLineEdit, QComboBox, QSpinBox, QCheckBox,
    QDialogButtonBox, QScrollArea, QMessageBox, QListWidget, QListWidgetItem
)

from database.models import Camera
from services.camera_repository import CameraRepository
from services.detection_pipeline import DetectionPipeline
from models.enums import ProtocoloCamera, TipoEPI, StatusCamera
from ui.widgets.camera_widget import CameraWidget


class CameraDialog(QDialog):
    """Formulário de cadastro/edição de câmera, incluindo EPIs obrigatórios."""

    def __init__(self, camera: Camera | None = None, parent=None) -> None:
        super().__init__(parent)
        self.camera = camera
        self.setWindowTitle("Editar Câmera" if camera else "Nova Câmera")
        self.setMinimumWidth(420)
        self._montar_ui()

    def _montar_ui(self) -> None:
        layout = QFormLayout(self)

        self.input_nome = QLineEdit(self.camera.nome if self.camera else "")
        layout.addRow("Nome:", self.input_nome)

        self.input_localizacao = QLineEdit(self.camera.localizacao if self.camera else "")
        layout.addRow("Localização:", self.input_localizacao)

        self.combo_protocolo = QComboBox()
        self.combo_protocolo.addItems([p.value for p in ProtocoloCamera])
        if self.camera:
            self.combo_protocolo.setCurrentText(self.camera.protocolo.value)
        layout.addRow("Protocolo:", self.combo_protocolo)

        self.input_url = QLineEdit(self.camera.url_rtsp if self.camera else "")
        self.input_url.setPlaceholderText("rtsp://usuario:senha@ip:porta/stream")
        layout.addRow("URL RTSP:", self.input_url)

        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(1, 30)
        self.spin_fps.setValue(self.camera.fps_alvo if self.camera else 10)
        layout.addRow("FPS alvo:", self.spin_fps)

        layout.addRow(QLabel("EPIs obrigatórios nesta câmera:"))
        self.checks_epi: dict[TipoEPI, QCheckBox] = {}
        epis_atuais = set()
        if self.camera:
            epis_atuais = set(CameraRepository.epis_obrigatorios_da_camera(self.camera.id))
        for epi in TipoEPI:
            cb = QCheckBox(epi.value.capitalize())
            cb.setChecked(epi in epis_atuais)
            self.checks_epi[epi] = cb
            layout.addRow(cb)

        botoes = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        layout.addRow(botoes)

    def obter_dados(self) -> dict:
        return {
            "nome": self.input_nome.text().strip(),
            "localizacao": self.input_localizacao.text().strip(),
            "protocolo": ProtocoloCamera(self.combo_protocolo.currentText()),
            "url_rtsp": self.input_url.text().strip(),
            "fps_alvo": self.spin_fps.value(),
            "epis_obrigatorios": [epi for epi, cb in self.checks_epi.items() if cb.isChecked()],
        }


class CamerasPage(QWidget):
    """Grid ao vivo + gerenciamento de câmeras."""

    def __init__(self, pipeline: DetectionPipeline, bridge, nivel_usuario) -> None:
        super().__init__()
        self.pipeline = pipeline
        self.bridge = bridge  # ui.pipeline_bridge.PipelineBridge - ponte thread-safe
        self.nivel_usuario = nivel_usuario
        self._widgets_camera: dict[int, CameraWidget] = {}
        self._montar_ui()
        self._carregar_cameras()

        # O pipeline (thread de background) chama bridge.emitir_frame(); o
        # sinal Qt entrega o resultado com segurança na thread da UI aqui:
        self.pipeline.registrar_callback_frame(self.bridge.emitir_frame)
        self.bridge.frame_processado.connect(self._on_frame_processado)
        self.bridge.status_alterado.connect(self._on_status_alterado)

    def _montar_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        topo = QHBoxLayout()
        titulo = QLabel("Câmeras")
        titulo.setStyleSheet("font-size: 22px; font-weight: 700;")
        topo.addWidget(titulo)
        topo.addStretch()

        btn_nova = QPushButton("+ Nova Câmera")
        btn_nova.clicked.connect(self._nova_camera)
        topo.addWidget(btn_nova)
        layout.addLayout(topo)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.grid = QGridLayout(container)
        self.grid.setSpacing(12)
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def _carregar_cameras(self) -> None:
        cameras = CameraRepository.listar_todas(apenas_ativas=True)
        colunas = 3
        for i, camera in enumerate(cameras):
            widget = CameraWidget(camera.id, camera.nome)
            self._widgets_camera[camera.id] = widget
            self.grid.addWidget(widget, i // colunas, i % colunas)
            self.pipeline.iniciar_camera(camera)

        self.pipeline.start_loop_processamento()

    def _nova_camera(self) -> None:
        dialog = CameraDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            dados = dialog.obter_dados()
            if not dados["nome"] or not dados["url_rtsp"]:
                QMessageBox.warning(self, "Campos obrigatórios", "Nome e URL RTSP são obrigatórios.")
                return

            camera = CameraRepository.criar(**dados)
            widget = CameraWidget(camera.id, camera.nome)
            self._widgets_camera[camera.id] = widget
            idx = len(self._widgets_camera) - 1
            self.grid.addWidget(widget, idx // 3, idx % 3)
            self.pipeline.iniciar_camera(camera)

    def _on_frame_processado(self, camera_id: int, resultado) -> None:
        """
        Slot conectado ao sinal `frame_processado` da PipelineBridge.
        Garantido pelo Qt para rodar na thread principal da UI, portanto
        é seguro atualizar o widget diretamente aqui.
        """
        widget = self._widgets_camera.get(camera_id)
        if widget:
            widget.atualizar_frame(resultado.frame_anotado)

    def _on_status_alterado(self, camera_id: int, status) -> None:
        widget = self._widgets_camera.get(camera_id)
        if widget:
            widget.atualizar_status(status)
