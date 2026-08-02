from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QPushButton, QHeaderView, QMessageBox, QDialog,
    QFormLayout, QLineEdit, QComboBox
)
from PySide6.QtCore import Qt
from core.security import UserService
from database.connection import get_session
from database.models import Usuario
from models.enums import NivelAcesso

class UserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Novo Usuário")
        self.setMinimumWidth(400)
        
        layout = QFormLayout(self)
        
        self.nome_input = QLineEdit()
        self.login_input = QLineEdit()
        self.email_input = QLineEdit()
        self.senha_input = QLineEdit()
        self.senha_input.setEchoMode(QLineEdit.Password)
        
        self.nivel_combo = QComboBox()
        for nivel in NivelAcesso:
            self.nivel_combo.addItem(nivel.value, userData=nivel)
            
        layout.addRow("Nome Completo:", self.nome_input)
        layout.addRow("Login:", self.login_input)
        layout.addRow("E-mail:", self.email_input)
        layout.addRow("Senha:", self.senha_input)
        layout.addRow("Nível de Acesso:", self.nivel_combo)
        
        botoes_layout = QHBoxLayout()
        btn_salvar = QPushButton("Salvar")
        btn_cancelar = QPushButton("Cancelar")
        
        btn_salvar.clicked.connect(self.accept)
        btn_cancelar.clicked.connect(self.reject)
        
        botoes_layout.addWidget(btn_salvar)
        botoes_layout.addWidget(btn_cancelar)
        
        layout.addRow(botoes_layout)
        
    def get_data(self):
        return {
            "nome_completo": self.nome_input.text().strip(),
            "login": self.login_input.text().strip(),
            "email": self.email_input.text().strip(),
            "senha_plana": self.senha_input.text().strip(),
            "nivel": self.nivel_combo.currentData()
        }


class UsersPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._montar_ui()
        self._carregar_usuarios()

    def _montar_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        
        topo = QHBoxLayout()
        titulo = QLabel("Gestão de Usuários")
        titulo.setStyleSheet("font-size: 20px; font-weight: bold;")
        topo.addWidget(titulo)
        
        topo.addStretch()
        
        btn_novo = QPushButton("+ Novo Usuário")
        btn_novo.setMinimumHeight(35)
        btn_novo.clicked.connect(self._novo_usuario)
        topo.addWidget(btn_novo)
        layout.addLayout(topo)

        self.tabela = QTableWidget(0, 6)
        self.tabela.setHorizontalHeaderLabels(["ID", "Nome", "Login", "E-mail", "Nível", "Status"])
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabela.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.tabela)
        
        botoes_acao_layout = QHBoxLayout()
        btn_alternar_status = QPushButton("Alternar Status (Ativar/Inativar)")
        btn_alternar_status.clicked.connect(self._alternar_status_usuario)
        
        botoes_acao_layout.addWidget(btn_alternar_status)
        botoes_acao_layout.addStretch()
        
        layout.addLayout(botoes_acao_layout)

    def _carregar_usuarios(self) -> None:
        with get_session() as session:
            usuarios = session.query(Usuario).order_by(Usuario.id).all()
            self.tabela.setRowCount(len(usuarios))
            for i, u in enumerate(usuarios):
                self.tabela.setItem(i, 0, QTableWidgetItem(str(u.id)))
                self.tabela.setItem(i, 1, QTableWidgetItem(u.nome_completo))
                self.tabela.setItem(i, 2, QTableWidgetItem(u.login))
                self.tabela.setItem(i, 3, QTableWidgetItem(u.email or "-"))
                self.tabela.setItem(i, 4, QTableWidgetItem(u.nivel_acesso.value))
                status = "Ativo" if u.ativo else "Inativo"
                item_status = QTableWidgetItem(status)
                if not u.ativo:
                    item_status.setForeground(Qt.red)
                self.tabela.setItem(i, 5, item_status)

    def _novo_usuario(self):
        dialog = UserDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if not data["nome_completo"] or not data["login"] or not data["senha_plana"]:
                QMessageBox.warning(self, "Erro", "Nome, Login e Senha são obrigatórios!")
                return
                
            try:
                UserService.criar_usuario(
                    nome_completo=data["nome_completo"],
                    login=data["login"],
                    email=data["email"],
                    senha_plana=data["senha_plana"],
                    nivel=data["nivel"]
                )
                self._carregar_usuarios()
                QMessageBox.information(self, "Sucesso", "Usuário criado com sucesso!")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao criar usuário: {str(e)}")
                
    def _alternar_status_usuario(self):
        linhas_selecionadas = self.tabela.selectedItems()
        if not linhas_selecionadas:
            QMessageBox.warning(self, "Aviso", "Selecione um usuário na tabela primeiro.")
            return
            
        linha = linhas_selecionadas[0].row()
        usuario_id = int(self.tabela.item(linha, 0).text())
        login = self.tabela.item(linha, 2).text()
        
        # Não permitir desativar a si mesmo ou o admin master, mas como é um exemplo simples, vamos apenas alternar.
        if login == "admin":
            QMessageBox.warning(self, "Aviso", "Não é possível inativar o usuário master.")
            return
            
        try:
            novo_status = UserService.alternar_status(usuario_id)
            self._carregar_usuarios()
            status_str = "ativado" if novo_status else "inativado"
            QMessageBox.information(self, "Sucesso", f"Usuário {login} foi {status_str}.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao alternar status: {str(e)}")
