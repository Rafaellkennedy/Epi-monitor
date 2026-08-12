"""
ui/pages/cameras_page.py
---------------------------
Tela de gest\u00e3o e monitoramento ao vivo de c\u00e2meras: exibe o grid com v\u00eddeo
de todas as c\u00e2meras cadastradas (com detec\u00e7\u00f5es desenhadas) e permite
cadastrar, editar e remover c\u00e2meras com suporte a m\u00faltiplos tipos de fonte
(IP/RTSP, arquivo de v\u00eddeo, webcam), localiza\u00e7\u00e3o e EPIs obrigat\u00f3rios.
"""

from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QDialog, QFormLayout, QLineEdit, QComboBox, QSpinBox, QCheckBox,
    QDialogButtonBox, QScrollArea, QMessageBox, QFileDialog, QStackedWidget,
    QFrame
)

from database.models import Camera
from services.camera_repository import CameraRepository
from services.detection_pipeline import DetectionPipeline
from models.enums import ProtocoloCamera, TipoEPI, StatusCamera, EPI_LABEL_PT_BR
from ui.widgets.camera_widget import CameraWidget


# ---------------------------------------------------------------------------
# Mapeamento entre tipo de fonte da UI e o protocolo/url_rtsp
# ---------------------------------------------------------------------------
_TIPO_FONTE_OPCOES = {
    "rtsp": "C\u00e2mera IP (RTSP)",
    "arquivo": "Arquivo de v\u00eddeo",
    "webcam": "Webcam",
}


def _inferir_tipo_fonte(url: str) -> str:
    """Deduz o tipo de fonte a partir da url_rtsp armazenada no banco."""
    if not url:
        return "rtsp"
    if url.startswith("rtsp://") or url.startswith("rtmp://"):
        return "rtsp"
    if url.isdigit():
        return "webcam"
    return "arquivo"


# ---------------------------------------------------------------------------
# Di\u00e1logo de cadastro/edi\u00e7\u00e3o de c\u00e2mera
# ---------------------------------------------------------------------------
class CameraDialog(QDialog):
    """Formul\u00e1rio completo de cadastro/edi\u00e7\u00e3o de c\u00e2mera."""

    def __init__(self, camera: Optional[Camera] = None, parent=None) -> None:
        super().__init__(parent)
        self.camera = camera
        self.setWindowTitle("Editar C\u00e2mera" if camera else "Nova C\u00e2mera")
        self.setMinimumWidth(480)
        self._montar_ui()
        if camera:
            self._preencher_campos(camera)

    # ------------------------------------------------------------------
    def _montar_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)

        # Nome
        self.input_nome = QLineEdit()
        self.input_nome.setPlaceholderText("Ex: C\u00e2mera Caldeira 2")
        form.addRow("Nome:", self.input_nome)

        # Tipo de fonte
        self.combo_tipo_fonte = QComboBox()
        for chave, rotulo in _TIPO_FONTE_OPCOES.items():
            self.combo_tipo_fonte.addItem(rotulo, chave)
        self.combo_tipo_fonte.currentIndexChanged.connect(self._alternar_campo_fonte)
        form.addRow("Tipo de fonte:", self.combo_tipo_fonte)

        # Stack com os campos de fonte contextual
        self.stack_fonte = QStackedWidget()

        # P\u00e1gina RTSP
        pagina_rtsp = QWidget()
        layout_rtsp = QHBoxLayout(pagina_rtsp)
        layout_rtsp.setContentsMargins(0, 0, 0, 0)
        self.input_url_rtsp = QLineEdit()
        self.input_url_rtsp.setPlaceholderText("rtsp://usuario:senha@ip:porta/stream")
        layout_rtsp.addWidget(self.input_url_rtsp)
        self.stack_fonte.addWidget(pagina_rtsp)  # index 0

        # P\u00e1gina Arquivo
        pagina_arquivo = QWidget()
        layout_arquivo = QHBoxLayout(pagina_arquivo)
        layout_arquivo.setContentsMargins(0, 0, 0, 0)
        self.input_arquivo = QLineEdit()
        self.input_arquivo.setPlaceholderText("/caminho/para/video.mp4")
        btn_procurar = QPushButton("Procurar\u2026")
        btn_procurar.setObjectName("secondaryButton")
        btn_procurar.clicked.connect(self._procurar_arquivo)
        layout_arquivo.addWidget(self.input_arquivo, 1)
        layout_arquivo.addWidget(btn_procurar)
        self.stack_fonte.addWidget(pagina_arquivo)  # index 1

        # P\u00e1gina Webcam
        pagina_webcam = QWidget()
        layout_webcam = QHBoxLayout(pagina_webcam)
        layout_webcam.setContentsMargins(0, 0, 0, 0)
        self.combo_webcam = QComboBox()
        for i in range(5):
            self.combo_webcam.addItem(f"\u00cdndice {i}", i)
        layout_webcam.addWidget(self.combo_webcam)
        layout_webcam.addStretch()
        self.stack_fonte.addWidget(pagina_webcam)  # index 2

        form.addRow("Fonte:", self.stack_fonte)

        # Localiza\u00e7\u00e3o
        self.input_localizacao = QLineEdit()
        self.input_localizacao.setPlaceholderText("Ex: Caldeira 2 \u2014 Piso 3")
        form.addRow("Localiza\u00e7\u00e3o:", self.input_localizacao)

        # FPS alvo
        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(1, 30)
        self.spin_fps.setValue(10)
        form.addRow("FPS alvo:", self.spin_fps)

        layout.addLayout(form)

        # EPIs obrigat\u00f3rios
        layout.addWidget(QLabel("EPIs obrigat\u00f3rios nesta c\u00e2mera:"))
        self.checks_epi: dict[TipoEPI, QCheckBox] = {}
        for epi in TipoEPI:
            cb = QCheckBox(EPI_LABEL_PT_BR.get(epi.value, epi.value.capitalize()))
            self.checks_epi[epi] = cb
            layout.addWidget(cb)

        # Bot\u00f5es
        botoes = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        botoes.accepted.connect(self._validar_e_aceitar)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)

    def _alternar_campo_fonte(self, index: int) -> None:
        self.stack_fonte.setCurrentIndex(index)

    def _procurar_arquivo(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Selecionar arquivo de v\u00eddeo", "",
            "V\u00eddeos (*.mp4 *.avi *.mkv *.mov *.webm);;Todos os arquivos (*)"
        )
        if caminho:
            self.input_arquivo.setText(caminho)

    def _preencher_campos(self, camera: Camera) -> None:
        self.input_nome.setText(camera.nome)
        self.input_localizacao.setText(camera.localizacao or "")
        self.spin_fps.setValue(camera.fps_alvo)

        tipo = _inferir_tipo_fonte(camera.url_rtsp)
        idx = list(_TIPO_FONTE_OPCOES.keys()).index(tipo)
        self.combo_tipo_fonte.setCurrentIndex(idx)

        if tipo == "rtsp":
            self.input_url_rtsp.setText(camera.url_rtsp)
        elif tipo == "arquivo":
            self.input_arquivo.setText(camera.url_rtsp)
        elif tipo == "webcam":
            try:
                indice = int(camera.url_rtsp)
                self.combo_webcam.setCurrentIndex(min(indice, 4))
            except (ValueError, TypeError):
                pass

        epis_atuais = set(CameraRepository.epis_obrigatorios_da_camera(camera.id))
        for epi, cb in self.checks_epi.items():
            cb.setChecked(epi in epis_atuais)

    def _validar_e_aceitar(self) -> None:
        dados = self.obter_dados()
        if not dados["nome"].strip():
            QMessageBox.warning(self, "Campo obrigat\u00f3rio", "O nome da c\u00e2mera \u00e9 obrigat\u00f3rio.")
            return
        fonte = self._obter_valor_fonte()
        if not fonte.strip():
            QMessageBox.warning(self, "Campo obrigat\u00f3rio", "A fonte (URL, arquivo ou \u00edndice) \u00e9 obrigat\u00f3ria.")
            return
        self.accept()

    def _obter_valor_fonte(self) -> str:
        tipo = self.combo_tipo_fonte.currentData()
        if tipo == "rtsp":
            return self.input_url_rtsp.text().strip()
        elif tipo == "arquivo":
            return self.input_arquivo.text().strip()
        elif tipo == "webcam":
            return str(self.combo_webcam.currentData())
        return ""

    def obter_dados(self) -> dict:
        return {
            "nome": self.input_nome.text().strip(),
            "localizacao": self.input_localizacao.text().strip(),
            "protocolo": ProtocoloCamera.RTSP,
            "url_rtsp": self._obter_valor_fonte(),
            "fps_alvo": self.spin_fps.value(),
            "epis_obrigatorios": [
                epi for epi, cb in self.checks_epi.items() if cb.isChecked()
            ],
        }


# ---------------------------------------------------------------------------
# P\u00e1gina de c\u00e2meras
# ---------------------------------------------------------------------------
class CamerasPage(QWidget):
    """Grid ao vivo + gerenciamento de c\u00e2meras."""

    def __init__(self, pipeline: DetectionPipeline, bridge, nivel_usuario) -> None:
        super().__init__()
        self.pipeline = pipeline
        self.bridge = bridge
        self.nivel_usuario = nivel_usuario
        self._widgets_camera: dict[int, CameraWidget] = {}
        self._camera_widgets_por_id: dict[int, QWidget] = {}  # wrapper widgets
        self._colunas = 3
        self._montar_ui()
        self._carregar_cameras()

        self.pipeline.registrar_callback_frame(self.bridge.emitir_frame)
        self.bridge.frame_processado.connect(self._on_frame_processado)
        self.bridge.status_alterado.connect(self._on_status_alterado)

    # ------------------------------------------------------------------
    def _montar_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Barra superior
        topo = QHBoxLayout()
        titulo = QLabel("C\u00e2meras")
        titulo.setStyleSheet("font-size: 22px; font-weight: 700;")
        topo.addWidget(titulo)
        topo.addStretch()

        btn_nova = QPushButton("+ Nova C\u00e2mera")
        btn_nova.clicked.connect(self._nova_camera)
        topo.addWidget(btn_nova)
        layout.addLayout(topo)

        # Label de estado vazio (exibido quando n\u00e3o h\u00e1 c\u00e2meras)
        self.label_vazio = QLabel(
            "Nenhuma c\u00e2mera cadastrada \u2014 adicione a primeira."
        )
        self.label_vazio.setAlignment(Qt.AlignCenter)
        self.label_vazio.setStyleSheet(
            "font-size: 15px; color: #6b7280; padding: 60px;"
        )
        self.label_vazio.setVisible(False)
        layout.addWidget(self.label_vazio)

        # Scroll area com grid
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        container = QWidget()
        self.grid = QGridLayout(container)
        self.grid.setSpacing(12)
        self.scroll.setWidget(container)
        layout.addWidget(self.scroll)

    # ------------------------------------------------------------------
    def _carregar_cameras(self) -> None:
        cameras = CameraRepository.listar_todas(apenas_ativas=True)
        self._reconstruir_grid(cameras)
        self.pipeline.start_loop_processamento()

    def _reconstruir_grid(self, cameras) -> None:
        # Limpa o grid atual
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._widgets_camera.clear()
        self._camera_widgets_por_id.clear()

        colunas = self._colunas
        for i, camera in enumerate(cameras):
            wrapper = self._criar_card_camera(camera)
            self.grid.addWidget(wrapper, i // colunas, i % colunas)

        tem_cameras = len(cameras) > 0
        self.label_vazio.setVisible(not tem_cameras)
        self.scroll.setVisible(tem_cameras)

    def _criar_card_camera(self, camera: Camera) -> QWidget:
        """Cria um card com v\u00eddeo ao vivo e a\u00e7\u00f5es de ger\u00eancia."""
        tipo = _inferir_tipo_fonte(camera.url_rtsp)

        widget_video = CameraWidget(
            camera.id,
            camera.nome,
            localizacao=camera.localizacao or "",
            tipo_fonte=tipo,
        )
        self._widgets_camera[camera.id] = widget_video

        # Inicia o pipeline para esta c\u00e2mera
        self.pipeline.iniciar_camera(camera)

        # Bot\u00f5es de a\u00e7\u00e3o
        botoes = QHBoxLayout()
        botoes.setSpacing(6)

        btn_editar = QPushButton("Editar")
        btn_editar.setObjectName("secondaryButton")
        btn_editar.setFixedHeight(28)
        btn_editar.clicked.connect(lambda _, c=camera: self._editar_camera(c))
        botoes.addWidget(btn_editar)

        btn_remover = QPushButton("Remover")
        btn_remover.setObjectName("dangerButton")
        btn_remover.setFixedHeight(28)
        btn_remover.clicked.connect(lambda _, c=camera: self._confirmar_remover_camera(c))
        botoes.addWidget(btn_remover)
        botoes.addStretch()

        # Wrapper com v\u00eddeo + botoes
        wrapper = QFrame()
        wrapper.setObjectName("card")
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 8)
        wrapper_layout.setSpacing(4)
        wrapper_layout.addWidget(widget_video)
        wrapper_layout.addLayout(botoes)

        self._camera_widgets_por_id[camera.id] = wrapper
        return wrapper

    # ------------------------------------------------------------------
    def _nova_camera(self) -> None:
        dialog = CameraDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            dados = dialog.obter_dados()
            camera = CameraRepository.criar(**dados)
            self._adicionar_camera_ao_grid(camera)

    def _editar_camera(self, camera: Camera) -> None:
        dialog = CameraDialog(camera=camera, parent=self)
        if dialog.exec() == QDialog.Accepted:
            dados = dialog.obter_dados()
            CameraRepository.atualizar(camera.id, **{
                k: v for k, v in dados.items() if k not in ("epis_obrigatorios",)
            })
            CameraRepository.atualizar_epis_obrigatorios(
                camera.id, dados["epis_obrigatorios"]
            )
            # Recarrega para refletir mudan\u00e7as
            self._carregar_cameras()

    def _confirmar_remover_camera(self, camera: Camera) -> None:
        resposta = QMessageBox.question(
            self,
            "Remover c\u00e2mera",
            f"Deseja realmente remover a c\u00e2mera \"{camera.nome}\"?\n\n"
            "Os eventos hist\u00f3ricos associados ser\u00e3o mantidos no banco de dados.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resposta == QMessageBox.Yes:
            self.pipeline.parar_camera(camera.id)
            CameraRepository.remover(camera.id)
            wrapper = self._camera_widgets_por_id.pop(camera.id, None)
            self._widgets_camera.pop(camera.id, None)
            if wrapper:
                self.grid.removeWidget(wrapper)
                wrapper.deleteLater()
            self._atualizar_visibilidade_vazio()

    def _adicionar_camera_ao_grid(self, camera: Camera) -> None:
        wrapper = self._criar_card_camera(camera)
        idx = len(self._camera_widgets_por_id) - 1
        self.grid.addWidget(wrapper, idx // self._colunas, idx % self._colunas)
        self._atualizar_visibilidade_vazio()
        self.pipeline.start_loop_processamento()

    def _atualizar_visibilidade_vazio(self) -> None:
        tem_cameras = len(self._camera_widgets_por_id) > 0
        self.label_vazio.setVisible(not tem_cameras)
        self.scroll.setVisible(tem_cameras)

    # ------------------------------------------------------------------
    def _on_frame_processado(self, camera_id: int, resultado) -> None:
        widget = self._widgets_camera.get(camera_id)
        if widget:
            widget.atualizar_frame(resultado.frame_anotado)

    def _on_status_alterado(self, camera_id: int, status) -> None:
        widget = self._widgets_camera.get(camera_id)
        if widget:
            widget.atualizar_status(status)