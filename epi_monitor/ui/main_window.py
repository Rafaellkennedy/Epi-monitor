"""
ui/main_window.py
--------------------
Janela principal da aplicação: layout com menu lateral (sidebar),
barra superior (usuário logado / notificações) e uma área central com
`QStackedWidget` alternando entre as páginas do sistema.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QStackedWidget, QButtonGroup, QFrame, QSystemTrayIcon, QMessageBox
)
from PySide6.QtGui import QIcon

from database.models import Usuario
from models.enums import NivelAcesso
from config.settings import settings

from services.camera_service import CameraManager
from services.camera_repository import CameraRepository
from services.alert_service import AlertService
from services.detection_pipeline import DetectionPipeline

from ui.pipeline_bridge import PipelineBridge
from ui.pages.dashboard_page import DashboardPage
from ui.pages.cameras_page import CamerasPage
from ui.pages.events_page import EventsPage
from ui.pages.settings_page import SettingsPage
from ui.pages.users_page import UsersPage
from ui.theme import apply_theme


class MainWindow(QMainWindow):
    def __init__(self, usuario: Usuario, app) -> None:
        super().__init__()
        self.usuario = usuario
        self.app = app  # referência ao QApplication, para trocar tema em runtime

        self.setWindowTitle(settings.ui.app_name)
        self.setMinimumSize(settings.ui.window_min_width, settings.ui.window_min_height)

        # --------------------------------------------------------------
        # Monta a infraestrutura de detecção (camadas de serviço)
        # --------------------------------------------------------------
        self.bridge = PipelineBridge()
        self.camera_manager = CameraManager()
        self.alert_service = AlertService(
            sound_player=self._tocar_som,
            notification_callback=self.bridge.emitir_alerta,
        )
        self.pipeline = DetectionPipeline(self.camera_manager, self.alert_service)

        self.bridge.alerta_disparado.connect(self._exibir_notificacao_alerta)

        self._montar_ui()

    # ----------------------------------------------------------------
    def _montar_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout_root = QHBoxLayout(central)
        layout_root.setContentsMargins(0, 0, 0, 0)
        layout_root.setSpacing(0)

        layout_root.addWidget(self._criar_sidebar())

        area_direita = QVBoxLayout()
        area_direita.setSpacing(0)
        area_direita.addWidget(self._criar_topbar())

        self.stack = QStackedWidget()
        self.pagina_dashboard = DashboardPage()
        self.pagina_cameras = CamerasPage(self.pipeline, self.bridge, self.usuario.nivel_acesso)
        self.pagina_eventos = EventsPage()
        self.pagina_config = SettingsPage()
        self.pagina_config.tema_alterado.connect(self._trocar_tema)
        self.pagina_usuarios = UsersPage()

        for pagina in (self.pagina_dashboard, self.pagina_cameras, self.pagina_eventos, self.pagina_config, self.pagina_usuarios):
            self.stack.addWidget(pagina)

        area_direita.addWidget(self.stack)

        container_direita = QWidget()
        container_direita.setLayout(area_direita)
        layout_root.addWidget(container_direita)

    def _criar_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 20, 12, 20)
        layout.setSpacing(6)

        logo = QLabel("🛡️  EPI Monitor")
        logo.setStyleSheet("font-size: 16px; font-weight: 800; padding: 8px 8px 20px 8px;")
        layout.addWidget(logo)

        self.grupo_botoes = QButtonGroup(self)
        self.grupo_botoes.setExclusive(True)

        botoes_info = [
            ("📊  Dashboard", 0),
            ("🎥  Câmeras", 1),
            ("📋  Eventos", 2),
            ("⚙️  Configurações", 3),
        ]
        if self.usuario.nivel_acesso == NivelAcesso.ADMINISTRADOR:
            botoes_info.append(("👥  Usuários", 4))
        for texto, indice in botoes_info:
            btn = QPushButton(texto)
            btn.setObjectName("sidebarButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, i=indice: self.stack.setCurrentIndex(i))
            self.grupo_botoes.addButton(btn)
            layout.addWidget(btn)

        self.grupo_botoes.buttons()[0].setChecked(True)
        layout.addStretch()

        btn_sair = QPushButton("⏻  Sair")
        btn_sair.setObjectName("sidebarButton")
        btn_sair.clicked.connect(self._confirmar_logout)
        layout.addWidget(btn_sair)

        return sidebar

    def _criar_topbar(self) -> QFrame:
        topbar = QFrame()
        topbar.setObjectName("topBar")
        topbar.setFixedHeight(56)
        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(20, 0, 20, 0)

        layout.addStretch()
        info_usuario = QLabel(f"{self.usuario.nome_completo}  •  {self.usuario.nivel_acesso.value.replace('_', ' ').title()}")
        info_usuario.setStyleSheet("font-size: 12px; color: #9498a3;")
        layout.addWidget(info_usuario)

        return topbar

    # ----------------------------------------------------------------
    def iniciar_monitoramento(self) -> None:
        """Chamado após a janela ser exibida: conecta às câmeras cadastradas."""
        cameras = CameraRepository.listar_todas(apenas_ativas=True)
        self.pipeline.iniciar_todas(cameras)

    def _trocar_tema(self, tema: str) -> None:
        apply_theme(self.app, tema)

    def _tocar_som(self, caminho_arquivo: str) -> None:
        """Reproduz o som de alerta usando QSoundEffect (não bloqueante)."""
        from PySide6.QtMultimedia import QSoundEffect
        from PySide6.QtCore import QUrl
        import os

        if not os.path.exists(caminho_arquivo):
            return
        efeito = QSoundEffect(self)
        efeito.setSource(QUrl.fromLocalFile(caminho_arquivo))
        efeito.setVolume(0.9)
        efeito.play()

    def _exibir_notificacao_alerta(self, dados: dict) -> None:
        """Mostra notificação visual de infração (chamado via sinal thread-safe)."""
        if self.tray_icon_disponivel():
            self.tray_icon.showMessage(
                "⚠ Infração de EPI detectada",
                dados.get("mensagem", ""),
                QSystemTrayIcon.Warning,
                6000,
            )

    def tray_icon_disponivel(self) -> bool:
        return hasattr(self, "tray_icon") and self.tray_icon is not None

    def _confirmar_logout(self) -> None:
        resposta = QMessageBox.question(self, "Sair", "Deseja realmente encerrar o sistema?")
        if resposta == QMessageBox.Yes:
            self.close()

    def closeEvent(self, event) -> None:
        self.pipeline.parar_tudo()
        event.accept()
