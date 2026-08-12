"""
ui/pages/events_page.py
--------------------------
Tela de Hist\u00f3rico de Eventos: lista infra\u00e7\u00f5es/conformidades registradas,
com filtros por c\u00e2mera, tipo e per\u00edodo, e permite visualizar a evid\u00eancia
(v\u00eddeo ou snapshot) em um di\u00e1logo com player de v\u00eddeo embutido e metadados.
"""

from __future__ import annotations

import json
import os
from typing import Optional, Sequence

from PySide6.QtCore import Qt, QUrl, QDate, QTime, QDateTime
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QSlider,
    QDateEdit, QSizePolicy, QFrame, QGridLayout, QStackedWidget
)

from services.event_service import EventService
from services.camera_repository import CameraRepository
from models.enums import TipoEvento, EPI_LABEL_PT_BR, TIPO_EVENTO_LABEL_PT_BR


# ---------------------------------------------------------------------------
# Di\u00e1logo de evid\u00eancia (v\u00eddeo + snapshot + metadados)
# ---------------------------------------------------------------------------
class EvidenceDialog(QDialog):
    """Exibe a evid\u00eancia de um evento: v\u00eddeo, snapshot e metadados."""

    def __init__(self, evento, parent=None) -> None:
        super().__init__(parent)
        self.evento = evento
        self._player: Optional[QMediaPlayer] = None
        self._audio: Optional[QAudioOutput] = None

        self.setWindowTitle("Evid\u00eancia da Infra\u00e7\u00e3o")
        self.setMinimumSize(720, 520)
        self._montar_ui()
        self._carregar_evidencia()

    def _montar_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # --- Metadados do evento ---
        meta_frame = QFrame()
        meta_frame.setObjectName("card")
        meta = QGridLayout(meta_frame)
        meta.setSpacing(6)

        nome_cam = self.evento.camera.nome if self.evento.camera else "C\u00e2mera removida"
        loc = (self.evento.camera.localizacao
               if self.evento.camera and self.evento.camera.localizacao
               else "\u2014")

        epis_ausentes = "\u2014"
        if self.evento.epis_ausentes_json:
            try:
                lista = json.loads(self.evento.epis_ausentes_json)
                epis_ausentes = ", ".join(EPI_LABEL_PT_BR.get(e, e) for e in lista) if lista else "\u2014"
            except (json.JSONDecodeError, TypeError):
                pass

        data_hora = self.evento.data_hora.strftime("%d/%m/%Y %H:%M:%S")

        linhas_meta = [
            ("C\u00e2mera:", nome_cam),
            ("Localiza\u00e7\u00e3o:", loc),
            ("Tipo:", TIPO_EVENTO_LABEL_PT_BR.get(self.evento.tipo_evento.value, self.evento.tipo_evento.value)),
            ("EPIs ausentes:", epis_ausentes),
            ("Data/Hora:", data_hora),
        ]
        for row, (chave, valor) in enumerate(linhas_meta):
            lbl_chave = QLabel(chave)
            lbl_chave.setStyleSheet("font-weight: 600; color: #9498a3;")
            lbl_valor = QLabel(valor)
            lbl_valor.setWordWrap(True)
            meta.addWidget(lbl_chave, row, 0, Qt.AlignTop)
            meta.addWidget(lbl_valor, row, 1)

        layout.addWidget(meta_frame)

        # --- \u00c1rea de m\u00eddia ---
        self.stack_midia = QStackedWidget()
        self.stack_midia.setMinimumHeight(300)

        # P\u00e1gina de v\u00eddeo
        pagina_video = QWidget()
        layout_video = QVBoxLayout(pagina_video)
        layout_video.setContentsMargins(0, 0, 0, 0)

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(640, 360)
        self.video_widget.setStyleSheet("background-color: #05060a; border-radius: 8px;")
        layout_video.addWidget(self.video_widget)

        # Controles de reprodu\u00e7\u00e3o
        controles = QHBoxLayout()
        controles.setSpacing(8)

        self.btn_play = QPushButton("\u25B6")
        self.btn_play.setFixedWidth(40)
        self.btn_play.clicked.connect(self._toggle_play)
        controles.addWidget(self.btn_play)

        self.label_tempo = QLabel("00:00 / 00:00")
        self.label_tempo.setStyleSheet("font-size: 12px; color: #b5b8c2; min-width: 90px;")
        controles.addWidget(self.label_tempo)

        self.slider_posicao = QSlider(Qt.Horizontal)
        self.slider_posicao.setRange(0, 0)
        self.slider_posicao.sliderMoved.connect(self._buscar_posicao)
        controles.addWidget(self.slider_posicao, 1)

        layout_video.addLayout(controles)
        self.stack_midia.addWidget(pagina_video)  # index 0

        # P\u00e1gina de snapshot (fallback)
        pagina_snapshot = QWidget()
        layout_snap = QVBoxLayout(pagina_snapshot)
        layout_snap.setContentsMargins(0, 0, 0, 0)
        self.label_snapshot = QLabel()
        self.label_snapshot.setAlignment(Qt.AlignCenter)
        self.label_snapshot.setStyleSheet("background-color: #05060a; border-radius: 8px;")
        layout_snap.addWidget(self.label_snapshot)
        self.stack_midia.addWidget(pagina_snapshot)  # index 1

        # P\u00e1gina de erro
        pagina_erro = QWidget()
        layout_erro = QVBoxLayout(pagina_erro)
        self.label_erro = QLabel()
        self.label_erro.setAlignment(Qt.AlignCenter)
        self.label_erro.setStyleSheet("font-size: 14px; color: #f87171; padding: 40px;")
        layout_erro.addWidget(self.label_erro)
        self.stack_midia.addWidget(pagina_erro)  # index 2

        layout.addWidget(self.stack_midia, 1)

        btn_fechar = QPushButton("Fechar")
        btn_fechar.clicked.connect(self.close)
        layout.addWidget(btn_fechar, alignment=Qt.AlignRight)

    def _carregar_evidencia(self) -> None:
        video_path = self.evento.caminho_video_clip
        snapshot_path = self.evento.caminho_snapshot

        if video_path and os.path.isfile(video_path):
            self._iniciar_player_video(video_path)
        elif snapshot_path and os.path.isfile(snapshot_path):
            self._mostrar_snapshot(snapshot_path)
        elif snapshot_path and not os.path.isfile(snapshot_path):
            self._mostrar_erro("Arquivo de evid\u00eancia n\u00e3o encontrado em disco.\n"
                              f"Caminho: {snapshot_path}")
        elif video_path and not os.path.isfile(video_path):
            self._mostrar_erro("Arquivo de v\u00eddeo n\u00e3o encontrado em disco.\n"
                              f"Caminho: {video_path}")
        else:
            self._mostrar_erro("Nenhuma evid\u00eancia dispon\u00edvel para este evento.")

    def _iniciar_player_video(self, video_path: str) -> None:
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)
        self._audio.setVolume(0.7)
        self._player.setVideoOutput(self.video_widget)

        self._player.setSource(QUrl.fromLocalFile(video_path))

        self._player.durationChanged.connect(self._on_duracao)
        self._player.positionChanged.connect(self._on_posicao)
        self._player.mediaStatusChanged.connect(self._on_status_midia)
        self._player.errorOccurred.connect(self._on_erro_player)

        self._player.play()
        self.btn_play.setText("\u23F8")
        self.stack_midia.setCurrentIndex(0)

    def _mostrar_snapshot(self, snapshot_path: str) -> None:
        pixmap = QPixmap(snapshot_path)
        if not pixmap.isNull():
            pixmap = pixmap.scaledToWidth(680, Qt.SmoothTransformation)
            self.label_snapshot.setPixmap(pixmap)
        else:
            self._mostrar_erro("N\u00e3o foi poss\u00edvel carregar a imagem.")
            return
        self.stack_midia.setCurrentIndex(1)

    def _mostrar_erro(self, mensagem: str) -> None:
        self.label_erro.setText(mensagem)
        self.stack_midia.setCurrentIndex(2)

    # --- Controles do player ---
    def _toggle_play(self) -> None:
        if self._player is None:
            return
        if self._player.playbackState() == QMediaPlayer.PlayingState:
            self._player.pause()
            self.btn_play.setText("\u25B6")
        else:
            self._player.play()
            self.btn_play.setText("\u23F8")

    def _buscar_posicao(self, posicao: int) -> None:
        if self._player:
            self._player.setPosition(posicao)

    def _on_duracao(self, duracao_ms: int) -> None:
        self.slider_posicao.setRange(0, duracao_ms)
        self._atualizar_label_tempo(0, duracao_ms)

    def _on_posicao(self, posicao_ms: int) -> None:
        if not self.slider_posicao.isSliderDown():
            self.slider_posicao.setValue(posicao_ms)
        if self._player:
            self._atualizar_label_tempo(posicao_ms, self._player.duration())

    def _on_status_midia(self, status) -> None:
        if status == QMediaPlayer.EndOfMedia:
            self.btn_play.setText("\u25B6")

    def _on_erro_player(self, erro, msg: str) -> None:
        self._mostrar_erro(f"Erro ao reproduzir v\u00eddeo: {msg}")

    @staticmethod
    def _formatar_tempo(ms: int) -> str:
        s = ms // 1000
        return f"{s // 60:02d}:{s % 60:02d}"

    def _atualizar_label_tempo(self, pos: int, dur: int) -> None:
        self.label_tempo.setText(
            f"{self._formatar_tempo(pos)} / {self._formatar_tempo(dur)}"
        )

    def closeEvent(self, event) -> None:
        if self._player:
            self._player.stop()
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# P\u00e1gina de eventos
# ---------------------------------------------------------------------------
class EventsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._eventos: Sequence = []
        self._montar_ui()
        self._carregar_eventos()

    def _montar_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        titulo = QLabel("Hist\u00f3rico de Eventos")
        titulo.setStyleSheet("font-size: 22px; font-weight: 700;")
        layout.addWidget(titulo)

        # Filtros
        filtros = QHBoxLayout()
        filtros.setSpacing(8)

        # C\u00e2mera
        filtros.addWidget(QLabel("C\u00e2mera:"))
        self.combo_camera = QComboBox()
        self.combo_camera.addItem("Todas as c\u00e2meras", None)
        for camera in CameraRepository.listar_todas():
            self.combo_camera.addItem(camera.nome, camera.id)
        filtros.addWidget(self.combo_camera)

        # Tipo
        filtros.addWidget(QLabel("Tipo:"))
        self.combo_tipo = QComboBox()
        self.combo_tipo.addItem("Todos os tipos", None)
        for tipo in TipoEvento:
            self.combo_tipo.addItem(TIPO_EVENTO_LABEL_PT_BR.get(tipo.value, tipo.value), tipo)
        filtros.addWidget(self.combo_tipo)

        # Per\u00edodo (datas)
        filtros.addWidget(QLabel("De:"))
        self.date_inicio = QDateEdit()
        self.date_inicio.setCalendarPopup(True)
        self.date_inicio.setDate(QDate.currentDate().addDays(-30))
        self.date_inicio.setDisplayFormat("dd/MM/yyyy")
        filtros.addWidget(self.date_inicio)

        filtros.addWidget(QLabel("At\u00e9:"))
        self.date_fim = QDateEdit()
        self.date_fim.setCalendarPopup(True)
        self.date_fim.setDate(QDate.currentDate())
        self.date_fim.setDisplayFormat("dd/MM/yyyy")
        filtros.addWidget(self.date_fim)

        btn_filtrar = QPushButton("Filtrar")
        btn_filtrar.clicked.connect(self._carregar_eventos)
        filtros.addWidget(btn_filtrar)
        filtros.addStretch()
        layout.addLayout(filtros)

        # Tabela
        self.tabela = QTableWidget(0, 6)
        self.tabela.setHorizontalHeaderLabels(
            ["Data/Hora", "C\u00e2mera", "Tipo", "EPIs Ausentes", "Confian\u00e7a", "Evid\u00eancia"]
        )
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setAlternatingRowColors(True)
        layout.addWidget(self.tabela)

        # Estado vazio
        self.label_vazio = QLabel("Nenhum evento encontrado para os filtros selecionados.")
        self.label_vazio.setAlignment(Qt.AlignCenter)
        self.label_vazio.setStyleSheet(
            "font-size: 15px; color: #6b7280; padding: 60px;"
        )
        self.label_vazio.setVisible(False)
        layout.addWidget(self.label_vazio)

    def _carregar_eventos(self) -> None:
        camera_id = self.combo_camera.currentData()
        tipo = self.combo_tipo.currentData()

        qd_inicio = self.date_inicio.date()
        qd_fim = self.date_fim.date()
        data_inicio = QDateTime(qd_inicio, QTime(0, 0, 0)).toPython()
        data_fim = QDateTime(qd_fim, QTime(23, 59, 59)).toPython()

        self._eventos = EventService.listar_eventos(
            camera_id=camera_id,
            tipo=tipo,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )

        self._popular_tabela()

    def _popular_tabela(self) -> None:
        self.tabela.setRowCount(len(self._eventos))

        for row, evento in enumerate(self._eventos):
            self.tabela.setItem(
                row, 0,
                QTableWidgetItem(evento.data_hora.strftime("%d/%m/%Y %H:%M:%S"))
            )
            nome_camera = evento.camera.nome if evento.camera else "-"
            self.tabela.setItem(row, 1, QTableWidgetItem(nome_camera))

            self.tabela.setItem(
                row, 2,
                QTableWidgetItem(TIPO_EVENTO_LABEL_PT_BR.get(evento.tipo_evento.value, evento.tipo_evento.value))
            )

            epis_ausentes = "-"
            if evento.epis_ausentes_json:
                try:
                    lista = json.loads(evento.epis_ausentes_json)
                    epis_ausentes = ", ".join(EPI_LABEL_PT_BR.get(e, e) for e in lista) if lista else "-"
                except (json.JSONDecodeError, TypeError):
                    pass
            self.tabela.setItem(row, 3, QTableWidgetItem(epis_ausentes))

            confianca = (
                f"{evento.confianca_media * 100:.1f}%"
                if evento.confianca_media else "-"
            )
            self.tabela.setItem(row, 4, QTableWidgetItem(confianca))

            tem_evidencia = bool(
                (evento.caminho_video_clip and os.path.isfile(evento.caminho_video_clip))
                or (evento.caminho_snapshot and os.path.isfile(evento.caminho_snapshot))
            )
            if tem_evidencia:
                btn_ver = QPushButton("Ver evid\u00eancia")
                btn_ver.clicked.connect(
                    lambda _, e=evento: self._abrir_evidencia(e)
                )
                self.tabela.setCellWidget(row, 5, btn_ver)
            else:
                self.tabela.setItem(row, 5, QTableWidgetItem("-"))

        self.label_vazio.setVisible(len(self._eventos) == 0)

    def _abrir_evidencia(self, evento) -> None:
        dialog = EvidenceDialog(evento, parent=self)
        dialog.exec()