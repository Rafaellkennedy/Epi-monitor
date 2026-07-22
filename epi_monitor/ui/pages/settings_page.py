"""
ui/pages/settings_page.py
----------------------------
Tela de configurações gerais do sistema: tema da interface, comportamento
de alertas (som/e-mail/cooldown) e política de retenção de evidências.
Os valores são persistidos na tabela `configuracoes` (chave/valor).
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QComboBox, QCheckBox, QSpinBox,
    QPushButton, QLabel, QMessageBox, QGroupBox
)

from sqlalchemy import select
from database.connection import get_session
from database.models import Configuracao


class SettingsPage(QWidget):
    tema_alterado = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._montar_ui()
        self._carregar_configuracoes()

    def _montar_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        titulo = QLabel("Configurações")
        titulo.setStyleSheet("font-size: 22px; font-weight: 700;")
        layout.addWidget(titulo)

        # --- Aparência ---
        grupo_aparencia = QGroupBox("Aparência")
        form_aparencia = QFormLayout(grupo_aparencia)
        self.combo_tema = QComboBox()
        self.combo_tema.addItems(["dark", "light"])
        form_aparencia.addRow("Tema:", self.combo_tema)
        layout.addWidget(grupo_aparencia)

        # --- Alertas ---
        grupo_alertas = QGroupBox("Alertas")
        form_alertas = QFormLayout(grupo_alertas)
        self.check_som = QCheckBox("Tocar alarme sonoro ao detectar infração")
        form_alertas.addRow(self.check_som)
        self.check_email = QCheckBox("Enviar alerta por e-mail")
        form_alertas.addRow(self.check_email)
        self.spin_cooldown = QSpinBox()
        self.spin_cooldown.setRange(5, 600)
        self.spin_cooldown.setSuffix(" segundos")
        form_alertas.addRow("Intervalo mínimo entre alertas repetidos:", self.spin_cooldown)
        layout.addWidget(grupo_alertas)

        # --- Armazenamento ---
        grupo_storage = QGroupBox("Armazenamento de Evidências")
        form_storage = QFormLayout(grupo_storage)
        self.spin_retencao = QSpinBox()
        self.spin_retencao.setRange(1, 3650)
        self.spin_retencao.setSuffix(" dias")
        form_storage.addRow("Retenção de fotos/vídeos:", self.spin_retencao)
        layout.addWidget(grupo_storage)

        btn_salvar = QPushButton("Salvar Configurações")
        btn_salvar.clicked.connect(self._salvar_configuracoes)
        layout.addWidget(btn_salvar)
        layout.addStretch()

    def _carregar_configuracoes(self) -> None:
        valores = self._ler_todas_configs()
        self.combo_tema.setCurrentText(valores.get("tema_padrao", "dark"))
        self.check_som.setChecked(valores.get("som_alertas_ativo", "true") == "true")
        self.check_email.setChecked(valores.get("email_alertas_ativo", "false") == "true")
        self.spin_cooldown.setValue(int(valores.get("cooldown_alerta_segundos", "30")))
        self.spin_retencao.setValue(int(valores.get("retencao_evidencias_dias", "90")))

    @staticmethod
    def _ler_todas_configs() -> dict:
        with get_session() as session:
            configs = session.scalars(select(Configuracao)).all()
            return {c.chave: c.valor for c in configs}

    def _salvar_configuracoes(self) -> None:
        novos_valores = {
            "tema_padrao": self.combo_tema.currentText(),
            "som_alertas_ativo": "true" if self.check_som.isChecked() else "false",
            "email_alertas_ativo": "true" if self.check_email.isChecked() else "false",
            "cooldown_alerta_segundos": str(self.spin_cooldown.value()),
            "retencao_evidencias_dias": str(self.spin_retencao.value()),
        }

        with get_session() as session:
            for chave, valor in novos_valores.items():
                config = session.query(Configuracao).filter_by(chave=chave).first()
                if config:
                    config.valor = valor
                else:
                    session.add(Configuracao(chave=chave, valor=valor))
            session.commit()

        self.tema_alterado.emit(novos_valores["tema_padrao"])
        QMessageBox.information(self, "Configurações", "Configurações salvas com sucesso.\n"
                                                          "Algumas alterações exigem reiniciar o sistema.")
