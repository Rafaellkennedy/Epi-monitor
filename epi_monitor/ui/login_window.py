"""
ui/login_window.py
-------------------
Janela de autenticação exibida antes de liberar acesso à aplicação
principal. Usa `core.security.AuthService` para validar credenciais.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QMessageBox
)

from core.security import AuthService
from database.models import Usuario


class LoginWindow(QWidget):
    """Emite `login_sucesso` com o objeto `Usuario` autenticado."""
    login_sucesso = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("EPI Monitor - Login")
        self.setMinimumSize(420, 520)
        self._montar_ui()

    def _montar_ui(self) -> None:
        layout_externo = QVBoxLayout(self)
        layout_externo.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(360)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(14)

        titulo = QLabel("EPI Monitor")
        titulo.setStyleSheet("font-size: 24px; font-weight: 800;")
        subtitulo = QLabel("Sistema de Monitoramento de EPIs por IA")
        subtitulo.setStyleSheet("color: #9498a3; font-size: 12px;")
        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(16)

        layout.addWidget(QLabel("Usuário"))
        self.input_login = QLineEdit()
        self.input_login.setPlaceholderText("Digite seu usuário")
        layout.addWidget(self.input_login)

        layout.addWidget(QLabel("Senha"))
        self.input_senha = QLineEdit()
        self.input_senha.setPlaceholderText("Digite sua senha")
        self.input_senha.setEchoMode(QLineEdit.Password)
        self.input_senha.returnPressed.connect(self._tentar_login)
        layout.addWidget(self.input_senha)

        layout.addSpacing(10)
        btn_entrar = QPushButton("Entrar")
        btn_entrar.clicked.connect(self._tentar_login)
        layout.addWidget(btn_entrar)

        rodape = QLabel("© EPI Monitor - Todos os direitos reservados")
        rodape.setStyleSheet("color: #6b6f7a; font-size: 10px;")
        rodape.setAlignment(Qt.AlignCenter)
        layout.addSpacing(20)
        layout.addWidget(rodape)

        layout_externo.addWidget(card)

    def _tentar_login(self) -> None:
        login = self.input_login.text().strip()
        senha = self.input_senha.text()

        if not login or not senha:
            QMessageBox.warning(self, "Campos obrigatórios", "Informe usuário e senha.")
            return

        resultado = AuthService.autenticar(login, senha)
        if resultado.sucesso:
            self.login_sucesso.emit(resultado.usuario)
        else:
            QMessageBox.critical(self, "Falha no login", resultado.mensagem)
            self.input_senha.clear()
