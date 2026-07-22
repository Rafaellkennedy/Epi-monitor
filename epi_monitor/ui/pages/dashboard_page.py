"""
ui/pages/dashboard_page.py
-----------------------------
Tela inicial do sistema: mostra cards com estatísticas agregadas
(total de infrações, conformidade, câmeras online) e um ranking das
câmeras com mais infrações no período, consultando `EventService`.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout,
    QTableWidget, QTableWidgetItem, QHeaderView
)

from services.event_service import EventService
from services.camera_repository import CameraRepository
from models.enums import StatusCamera


def _card(titulo: str, valor: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    frame.setMinimumHeight(100)
    layout = QVBoxLayout(frame)
    lbl_titulo = QLabel(titulo.upper())
    lbl_titulo.setObjectName("cardTitle")
    lbl_valor = QLabel(valor)
    lbl_valor.setObjectName("cardValue")
    layout.addWidget(lbl_titulo)
    layout.addWidget(lbl_valor)
    layout.addStretch()
    frame.lbl_valor = lbl_valor  # referência para atualização posterior
    return frame


class DashboardPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._montar_ui()
        self._atualizar_dados()

        # Atualiza estatísticas periodicamente (a cada 30s)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._atualizar_dados)
        self._timer.start(30_000)

    def _montar_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        titulo = QLabel("Dashboard")
        titulo.setStyleSheet("font-size: 22px; font-weight: 700;")
        layout.addWidget(titulo)

        grid_cards = QGridLayout()
        grid_cards.setSpacing(16)
        self.card_infracoes = _card("Infrações (7 dias)", "-")
        self.card_conformidade = _card("Taxa de conformidade", "-")
        self.card_cameras_online = _card("Câmeras online", "-")
        self.card_total_eventos = _card("Total de eventos", "-")
        grid_cards.addWidget(self.card_infracoes, 0, 0)
        grid_cards.addWidget(self.card_conformidade, 0, 1)
        grid_cards.addWidget(self.card_cameras_online, 0, 2)
        grid_cards.addWidget(self.card_total_eventos, 0, 3)
        layout.addLayout(grid_cards)

        subtitulo = QLabel("Ranking de câmeras com mais infrações")
        subtitulo.setStyleSheet("font-size: 16px; font-weight: 600; margin-top: 8px;")
        layout.addWidget(subtitulo)

        self.tabela_ranking = QTableWidget(0, 2)
        self.tabela_ranking.setHorizontalHeaderLabels(["Câmera", "Infrações"])
        self.tabela_ranking.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tabela_ranking.verticalHeader().setVisible(False)
        self.tabela_ranking.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela_ranking.setAlternatingRowColors(True)
        layout.addWidget(self.tabela_ranking)

    def _atualizar_dados(self) -> None:
        stats = EventService.estatisticas_dashboard(dias=7)
        self.card_infracoes.lbl_valor.setText(str(stats["total_infracoes"]))
        self.card_conformidade.lbl_valor.setText(f"{stats['taxa_conformidade']}%")
        self.card_total_eventos.lbl_valor.setText(
            str(stats["total_infracoes"] + stats["total_conformidade"])
        )

        cameras = CameraRepository.listar_todas()
        online = sum(1 for c in cameras if c.status == StatusCamera.ONLINE)
        self.card_cameras_online.lbl_valor.setText(f"{online}/{len(cameras)}")

        ranking = stats["ranking_cameras"]
        self.tabela_ranking.setRowCount(len(ranking))
        for row, item in enumerate(ranking):
            self.tabela_ranking.setItem(row, 0, QTableWidgetItem(item["camera"]))
            self.tabela_ranking.setItem(row, 1, QTableWidgetItem(str(item["infracoes"])))
