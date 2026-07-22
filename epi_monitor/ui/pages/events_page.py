"""
ui/pages/events_page.py
--------------------------
Tela de Histórico de Eventos: lista infrações/conformidades registradas,
com filtro por câmera/tipo/período, e permite visualizar o snapshot da
infração em um diálogo.
"""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog
)

from services.event_service import EventService
from services.camera_repository import CameraRepository
from models.enums import TipoEvento


class SnapshotDialog(QDialog):
    """Exibe a imagem do snapshot de uma infração em tamanho ampliado."""

    def __init__(self, caminho_imagem: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Evidência da Infração")
        layout = QVBoxLayout(self)
        label = QLabel()
        pixmap = QPixmap(caminho_imagem)
        if not pixmap.isNull():
            pixmap = pixmap.scaledToWidth(700, Qt.SmoothTransformation)
            label.setPixmap(pixmap)
        else:
            label.setText("Não foi possível carregar a imagem.")
        layout.addWidget(label)


class EventsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._montar_ui()
        self._carregar_eventos()

    def _montar_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        titulo = QLabel("Histórico de Eventos")
        titulo.setStyleSheet("font-size: 22px; font-weight: 700;")
        layout.addWidget(titulo)

        filtros = QHBoxLayout()
        self.combo_camera = QComboBox()
        self.combo_camera.addItem("Todas as câmeras", None)
        for camera in CameraRepository.listar_todas():
            self.combo_camera.addItem(camera.nome, camera.id)
        filtros.addWidget(QLabel("Câmera:"))
        filtros.addWidget(self.combo_camera)

        self.combo_tipo = QComboBox()
        self.combo_tipo.addItem("Todos os tipos", None)
        for tipo in TipoEvento:
            self.combo_tipo.addItem(tipo.value.capitalize(), tipo)
        filtros.addWidget(QLabel("Tipo:"))
        filtros.addWidget(self.combo_tipo)

        btn_filtrar = QPushButton("Filtrar")
        btn_filtrar.clicked.connect(self._carregar_eventos)
        filtros.addWidget(btn_filtrar)
        filtros.addStretch()
        layout.addLayout(filtros)

        self.tabela = QTableWidget(0, 6)
        self.tabela.setHorizontalHeaderLabels(
            ["Data/Hora", "Câmera", "Tipo", "EPIs Ausentes", "Confiança", "Evidência"]
        )
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setAlternatingRowColors(True)
        layout.addWidget(self.tabela)

    def _carregar_eventos(self) -> None:
        camera_id = self.combo_camera.currentData()
        tipo = self.combo_tipo.currentData()
        eventos = EventService.listar_eventos(camera_id=camera_id, tipo=tipo)

        self.tabela.setRowCount(len(eventos))
        for row, evento in enumerate(eventos):
            self.tabela.setItem(row, 0, QTableWidgetItem(evento.data_hora.strftime("%d/%m/%Y %H:%M:%S")))
            nome_camera = evento.camera.nome if evento.camera else "-"
            self.tabela.setItem(row, 1, QTableWidgetItem(nome_camera))
            self.tabela.setItem(row, 2, QTableWidgetItem(evento.tipo_evento.value.capitalize()))

            epis_ausentes = "-"
            if evento.epis_ausentes_json:
                try:
                    lista = json.loads(evento.epis_ausentes_json)
                    epis_ausentes = ", ".join(lista) if lista else "-"
                except (json.JSONDecodeError, TypeError):
                    pass
            self.tabela.setItem(row, 3, QTableWidgetItem(epis_ausentes))

            confianca = f"{evento.confianca_media * 100:.1f}%" if evento.confianca_media else "-"
            self.tabela.setItem(row, 4, QTableWidgetItem(confianca))

            if evento.caminho_snapshot:
                btn_ver = QPushButton("Ver evidência")
                btn_ver.clicked.connect(lambda _, p=evento.caminho_snapshot: self._abrir_snapshot(p))
                self.tabela.setCellWidget(row, 5, btn_ver)
            else:
                self.tabela.setItem(row, 5, QTableWidgetItem("-"))

    def _abrir_snapshot(self, caminho: str) -> None:
        dialog = SnapshotDialog(caminho, parent=self)
        dialog.exec()
