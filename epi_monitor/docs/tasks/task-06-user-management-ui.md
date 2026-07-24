# Task 06: Interface Gráfica de Gestão de Usuários (CRUD de Usuários)

## 📌 Informações da Task & Git Flow

- **ID:** TASK-06
- **Título:** Interface Gráfica para Administração de Usuários e Controle de Acesso (RBAC)
- **Branch Recomendada:** `feature/user-management-crud`
- **Base Branch:** `main` ou `develop`
- **Arquivos Afetados:**
  - `ui/pages/users_page.py` (Novo arquivo)
  - [ui/main_window.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/ui/main_window.py)
  - [core/security.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/core/security.py)

---

## 🔴 1. O que está errado (Diagnóstico do Problema)

### Sintoma
Não existe nenhuma forma visual no aplicativo para cadastrar novos funcionários, alterar senhas esquecidas, mudar permissões (Técnico de Segurança, Operador, Admin) ou desativar contas de funcionários desligados da empresa.

### Causa Raiz
A camada de segurança (`core/security.py`) e os modelos de banco (`Usuario`) foram criados no backend, mas o desenvolvimento da interface gráfica da tela de **Gestão de Usuários** não foi finalizado. Apenas o script de seed inicial (`scripts/setup_database.py`) insere o usuário admin default.

---

## 🟢 2. Caminho para a Solução (Guia de Refatoração)

### Estratégia de Refatoração:
1. **Adicionar Serviço de Usuários (`UserService`)**: Criar métodos CRUD estáticos para listar, criar, editar e resetar a senha de usuários usando `hash_password()`.
2. **Criar a Página `UsersPage` em `ui/pages/users_page.py`**:
   - Tabela com lista de usuários, e-mail, nível de acesso e status (Ativo/Inativo).
   - Diálogo `UserDialog` para cadastro e edição.
   - Botão para redefinir senha e alternar status (Ativar/Desativar).
3. **Integrar na `MainWindow`**: Exibir o botão "👥 Usuários" no menu lateral **apenas** quando o usuário logado tiver nível `NivelAcesso.ADMINISTRADOR`.

### Passo a Passo de Código:

#### Alteração 1: Método `UserService` em [`core/security.py`](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/core/security.py)
```python
class UserService:
    @staticmethod
    def criar_usuario(nome_completo: str, login: str, email: str, senha_plana: str, nivel: NivelAcesso) -> Usuario:
        with get_session() as session:
            novo = Usuario(
                nome_completo=nome_completo,
                login=login,
                email=email,
                senha_hash=hash_password(senha_plana),
                nivel_acesso=nivel,
                ativo=True
            )
            session.add(novo)
            session.commit()
            session.refresh(novo)
            session.expunge(novo)
            return novo

    @staticmethod
    def alternar_status(usuario_id: int) -> bool:
        with get_session() as session:
            usr = session.get(Usuario, usuario_id)
            if usr:
                usr.ativo = not usr.ativo
                session.commit()
                return usr.ativo
            return False
```

#### Alteração 2: Criar `ui/pages/users_page.py`
```python
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QPushButton, QHeaderView, QMessageBox, QDialog
)
from core.security import UserService
from database.connection import get_session
from database.models import Usuario

class UsersPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._montar_ui()
        self._carregar_usuarios()

    def _montar_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        
        topo = QHBoxLayout()
        topo.addWidget(QLabel("Gestão de Usuários"))
        btn_novo = QPushButton("+ Novo Usuário")
        btn_novo.clicked.connect(self._novo_usuario)
        topo.addWidget(btn_novo)
        layout.addLayout(topo)

        self.tabela = QTableWidget(0, 5)
        self.tabela.setHorizontalHeaderLabels(["Nome", "Login", "E-mail", "Nível", "Status"])
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tabela)

    def _carregar_usuarios(self) -> None:
        with get_session() as session:
            usuarios = session.query(Usuario).all()
            self.tabela.setRowCount(len(usuarios))
            for i, u in enumerate(usuarios):
                self.tabela.setItem(i, 0, QTableWidgetItem(u.nome_completo))
                self.tabela.setItem(i, 1, QTableWidgetItem(u.login))
                self.tabela.setItem(i, 2, QTableWidgetItem(u.email or "-"))
                self.tabela.setItem(i, 3, QTableWidgetItem(u.nivel_acesso.value))
                self.tabela.setItem(i, 4, QTableWidgetItem("Ativo" if u.ativo else "Inativo"))
```

---

## 🧪 3. Plano de Testes (Antes de Fazer Merge)

### A. Teste Unitário (`tests/test_user_service.py`)
```python
import pytest
from core.security import UserService, AuthService
from models.enums import NivelAcesso

def test_criar_e_autenticar_novo_usuario(db_session):
    user = UserService.criar_usuario("João Silva", "joaos", "joao@usina.com", "senha123", NivelAcesso.OPERADOR)
    assert user.id is not None
    
    # Valida login do novo usuário
    res = AuthService.autenticar("joaos", "senha123")
    assert res.sucesso is True
```

---

## 🔀 4. Git Flow & Checklist de Pull Request (PR)

### Comandos Git para abrir a Branch:
```bash
git checkout main
git pull origin main
git checkout -b feature/user-management-crud
```

### Mensagem de Commit Padronizada:
`feat(ui): add UsersPage UI and UserService for managing user accounts`

### Critérios para Aprovação do PR:
- [ ] Teste unitário de criação e autenticação de usuários aprovado.
- [ ] A aba "Usuários" aparece apenas para usuários logados como `Administrador`.
