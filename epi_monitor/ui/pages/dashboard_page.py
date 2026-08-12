"""
ui/pages/dashboard_page.py
-----------------------------
Tela inicial do sistema: cards com estat\u00edsticas agregadas, gr\u00e1fico de
infra\u00e7\u00f5es por dia (linha/\u00e1rea), ranking visual por c\u00e2mera, ranking
por localiza\u00e7\u00e3o e seletor de per\u00edodo (7/30/90 dias).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QDateTime, QDate
from PySide6.QtGui import QColor, QBrush, QPen, QLinearGradient, QFont
from PySide6.QtCharts import (
    QChart, QChartView, QLineSeries, QBarSeries, QBarSet,
    QBarCategoryAxis, QValueAxis, QDateTimeAxis, QAreaSeries,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QSizePolicy
)

from services.event_service import EventService
from services.camera_repository import CameraRepository
from models.enums import StatusCamera


# ---------------------------------------------------------------------------
# Cores consistentes com o tema dark (ui/theme.py)
# ---------------------------------------------------------------------------
_COR_FUNDO_CARD = QColor("#1a1d24")
_COR_TEXTO = QColor("#e8e9ec")
_COR_TEXTO_SEC = QColor("#9498a3")
_COR_GRADE = QColor("#2c2f3a")
_COR_AZUL = QColor("#2563eb")
_COR_AZUL_CLARO = QColor("#60a5fa")
_COR_VERDE = QColor("#34d399")
_COR_VERMELHO = QColor("#f87171")
_COR_LARANJA = QColor("#fbbf24")


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
    frame.lbl_valor = lbl_valor
    return frame


def _criar_chart_view() -> QChartView:
    """Factory de QChartView com estilo consistente ao tema escuro."""
    chart = QChart()
    chart.setBackgroundBrush(QBrush(_COR_FUNDO_CARD))
    chart.setTitleBrush(QBrush(_COR_TEXTO))
    chart.legend().setLabelBrush(QBrush(_COR_TEXTO_SEC))
    chart.setBackgroundVisible(True)
    chart.setPlotAreaBackgroundVisible(True)
    chart.setPlotAreaBackgroundBrush(QBrush(_COR_FUNDO_CARD))
    chart.legend().setVisible(True)
    chart.legend().setAlignment(Qt.AlignBottom)

    view = QChartView(chart)
    view.setRenderHint(QChartView.Antialiasing)
    view.setMinimumHeight(280)
    view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return view


class DashboardPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._dias = 7
        self._montar_ui()
        self._atualizar_dados()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._atualizar_dados)
        self._timer.start(30_000)

    # ------------------------------------------------------------------
    def _montar_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # T\u00edtulo + seletor de per\u00edodo
        topo = QHBoxLayout()
        titulo = QLabel("Dashboard")
        titulo.setStyleSheet("font-size: 22px; font-weight: 700;")
        topo.addWidget(titulo)
        topo.addStretch()

        lbl_periodo = QLabel("Per\u00edodo:")
        lbl_periodo.setStyleSheet("color: #9498a3;")
        topo.addWidget(lbl_periodo)

        self.combo_periodo = QComboBox()
        self.combo_periodo.addItem("\u00daltimos 7 dias", 7)
        self.combo_periodo.addItem("\u00daltimos 30 dias", 30)
        self.combo_periodo.addItem("\u00daltimos 90 dias", 90)
        self.combo_periodo.currentIndexChanged.connect(self._on_periodo_alterado)
        topo.addWidget(self.combo_periodo)
        layout.addLayout(topo)

        # Cards de resumo
        grid_cards = QGridLayout()
        grid_cards.setSpacing(16)
        self.card_infracoes = _card("Infra\u00e7\u00f5es (7 dias)", "-")
        self.card_conformidade = _card("Taxa de conformidade", "-")
        self.card_cameras_online = _card("C\u00e2meras online", "-")
        self.card_total_eventos = _card("Total de eventos", "-")
        grid_cards.addWidget(self.card_infracoes, 0, 0)
        grid_cards.addWidget(self.card_conformidade, 0, 1)
        grid_cards.addWidget(self.card_cameras_online, 0, 2)
        grid_cards.addWidget(self.card_total_eventos, 0, 3)
        layout.addLayout(grid_cards)

        # --- Gr\u00e1fico de linha: infra\u00e7\u00f5es por dia ---
        self.label_grafico_linha = QLabel("Infra\u00e7\u00f5es por dia")
        self.label_grafico_linha.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(self.label_grafico_linha)

        self.chart_view_linha = _criar_chart_view()
        layout.addWidget(self.chart_view_linha)

        # --- Ranking por c\u00e2mera (barras horizontais) ---
        painel_inferior = QHBoxLayout()
        painel_inferior.setSpacing(16)

        # Painel esquerdo: barras por c\u00e2mera
        painel_esq = QVBoxLayout()
        lbl_ranking = QLabel("Infra\u00e7\u00f5es por c\u00e2mera")
        lbl_ranking.setStyleSheet("font-size: 16px; font-weight: 600;")
        painel_esq.addWidget(lbl_ranking)

        self.chart_view_barras = _criar_chart_view()
        painel_esq.addWidget(self.chart_view_barras)
        painel_inferior.addLayout(painel_esq, 1)

        # Painel direito: barras por localiza\u00e7\u00e3o
        painel_dir = QVBoxLayout()
        lbl_local = QLabel("Infra\u00e7\u00f5es por localiza\u00e7\u00e3o")
        lbl_local.setStyleSheet("font-size: 16px; font-weight: 600;")
        painel_dir.addWidget(lbl_local)

        self.chart_view_local = _criar_chart_view()
        painel_dir.addWidget(self.chart_view_local)
        painel_inferior.addLayout(painel_dir, 1)

        layout.addLayout(painel_inferior)

        # Estado vazio para gr\u00e1ficos
        self.label_vazio_local = QLabel("Nenhum dado de localiza\u00e7\u00e3o dispon\u00edvel.")
        self.label_vazio_local.setAlignment(Qt.AlignCenter)
        self.label_vazio_local.setStyleSheet("font-size: 13px; color: #6b7280; padding: 20px;")
        self.label_vazio_local.setVisible(False)
        layout.addWidget(self.label_vazio_local)

    # ------------------------------------------------------------------
    def _on_periodo_alterado(self) -> None:
        self._dias = self.combo_periodo.currentData()
        self._atualizar_dados()

    def _atualizar_dados(self) -> None:
        stats = EventService.estatisticas_dashboard(dias=self._dias)

        # Cards
        self.card_infracoes.lbl_valor.setText(str(stats["total_infracoes"]))
        self.card_conformidade.lbl_valor.setText(f"{stats['taxa_conformidade']}%")
        self.card_total_eventos.lbl_valor.setText(
            str(stats["total_infracoes"] + stats["total_conformidade"])
        )

        cameras = CameraRepository.listar_todas()
        online = sum(1 for c in cameras if c.status == StatusCamera.ONLINE)
        self.card_cameras_online.lbl_valor.setText(f"{online}/{len(cameras)}")

        # Atualiza r\u00f3tulo do card de infra\u00e7\u00f5es com o per\u00edodo
        self.card_infracoes.findChild(QLabel).setText(
            f"INFRA\u00c7\u00d5ES ({self._dias} DIAS)"
        )

        # Gr\u00e1fico de linha/area: infra\u00e7\u00f5es por dia
        self._atualizar_grafico_linha(stats.get("serie_temporal", []))

        # Gr\u00e1fico de barras: ranking por c\u00e2mera
        self._atualizar_grafico_barras_camera(stats.get("ranking_cameras", []))

        # Gr\u00e1fico de barras: infra\u00e7\u00f5es por localiza\u00e7\u00e3o
        self._atualizar_grafico_local(stats.get("infracoes_por_local", []))

    # ------------------------------------------------------------------
    # Gr\u00e1fico de linha/\u00e1rea: s\u00e9rie temporal
    # ------------------------------------------------------------------
    def _atualizar_grafico_linha(self, serie: list) -> None:
        chart = self.chart_view_linha.chart()
        chart.removeAllSeries()
        # Remove eixos antigos
        for axis in chart.axes():
            chart.removeAxis(axis)

        if not serie:
            return

        # S\u00e9rie de linha
        line = QLineSeries()
        line.setName("Infra\u00e7\u00f5es")
        line.setPen(QPen(_COR_AZUL, 2))
        line.setPointsVisible(True)
        line.setPointLabelsVisible(True)
        line.setPointLabelsFormat("@yPoint")

        for ponto in serie:
            dt = QDateTime.fromString(ponto["dia"], "yyyy-MM-dd")
            if dt.isValid():
                line.append(dt.toMSecsSinceEpoch(), ponto["infracoes"])

        chart.addSeries(line)

        # Eixo X (datas)
        eixo_x = QDateTimeAxis()
        eixo_x.setFormat("dd/MM")
        eixo_x.setTitleText("Data")
        eixo_x.setTitleBrush(QBrush(_COR_TEXTO_SEC))
        eixo_x.setLabelsColor(_COR_TEXTO_SEC)
        eixo_x.setGridLineColor(_COR_GRADE)
        chart.addAxis(eixo_x, Qt.AlignBottom)
        line.attachAxis(eixo_x)

        # Eixo Y
        eixo_y = QValueAxis()
        eixo_y.setTitleText("Infra\u00e7\u00f5es")
        eixo_y.setTitleBrush(QBrush(_COR_TEXTO_SEC))
        eixo_y.setLabelsColor(_COR_TEXTO_SEC)
        eixo_y.setGridLineColor(_COR_GRADE)
        eixo_y.setLabelFormat("%d")
        chart.addAxis(eixo_y, Qt.AlignLeft)
        line.attachAxis(eixo_y)

        chart.setTitle("")

    # ------------------------------------------------------------------
    # Gr\u00e1fico de barras horizontais: ranking por c\u00e2mera
    # ------------------------------------------------------------------
    def _atualizar_grafico_barras_camera(self, ranking: list) -> None:
        chart = self.chart_view_barras.chart()
        chart.removeAllSeries()
        for axis in chart.axes():
            chart.removeAxis(axis)

        if not ranking:
            return

        bar_set = QBarSet("Infra\u00e7\u00f5es")
        bar_set.setColor(_COR_AZUL)
        bar_set.setBorderColor(_COR_AZUL_CLARO)

        categorias = []
        for item in ranking:
            categorias.append(item["camera"])
            bar_set.append(item["infracoes"])

        series = QBarSeries()
        series.append(bar_set)
        series.setLabelsVisible(True)
        series.setLabelsPosition(QBarSeries.LabelsInsideEnd)
        series.setLabelsFormat("@value")
        chart.addSeries(series)

        eixo_y = QBarCategoryAxis()
        eixo_y.append(categorias)
        eixo_y.setLabelsColor(_COR_TEXTO_SEC)
        eixo_y.setGridLineColor(_COR_GRADE)
        chart.addAxis(eixo_y, Qt.AlignLeft)
        series.attachAxis(eixo_y)

        eixo_x = QValueAxis()
        eixo_x.setLabelsColor(_COR_TEXTO_SEC)
        eixo_x.setGridLineColor(_COR_GRADE)
        eixo_x.setLabelFormat("%d")
        chart.addAxis(eixo_x, Qt.AlignBottom)
        series.attachAxis(eixo_x)

        chart.setTitle("")
        chart.legend().setVisible(False)

    # ------------------------------------------------------------------
    # Gr\u00e1fico de barras: infra\u00e7\u00f5es por localiza\u00e7\u00e3o
    # ------------------------------------------------------------------
    def _atualizar_grafico_local(self, locais: list) -> None:
        chart = self.chart_view_local.chart()
        chart.removeAllSeries()
        for axis in chart.axes():
            chart.removeAxis(axis)

        if not locais:
            return

        bar_set = QBarSet("Infra\u00e7\u00f5es")
        bar_set.setColor(_COR_LARANJA)
        bar_set.setBorderColor(_COR_LARANJA)

        categorias = []
        for item in locais:
            categorias.append(item["local"])
            bar_set.append(item["infracoes"])

        series = QBarSeries()
        series.append(bar_set)
        series.setLabelsVisible(True)
        series.setLabelsPosition(QBarSeries.LabelsInsideEnd)
        series.setLabelsFormat("@value")
        chart.addSeries(series)

        eixo_y = QBarCategoryAxis()
        eixo_y.append(categorias)
        eixo_y.setLabelsColor(_COR_TEXTO_SEC)
        eixo_y.setGridLineColor(_COR_GRADE)
        chart.addAxis(eixo_y, Qt.AlignLeft)
        series.attachAxis(eixo_y)

        eixo_x = QValueAxis()
        eixo_x.setLabelsColor(_COR_TEXTO_SEC)
        eixo_x.setGridLineColor(_COR_GRADE)
        eixo_x.setLabelFormat("%d")
        chart.addAxis(eixo_x, Qt.AlignBottom)
        series.attachAxis(eixo_x)

        chart.setTitle("")
        chart.legend().setVisible(False)