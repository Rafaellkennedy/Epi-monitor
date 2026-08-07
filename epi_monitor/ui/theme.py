"""
ui/theme.py
-----------
Define os temas visuais (dark/light) via QSS.

O que mudou em relação à versão anterior:
- Estados de interação completos (hover/pressed/focus/disabled) em TODOS
  os controles interativos — antes só QPushButton tinha :hover, então
  inputs, combos e itens de tabela pareciam "mortos" ao interagir.
- Espaçamento e raio de borda padronizados (8px/12px) em vez de valores
  soltos, para os cards e tabelas não parecerem de telas diferentes.
- Cores semânticas para sucesso/erro/aviso reaproveitadas pelos Chips e
  Toasts (ui/widgets/common.py e ui/widgets/toast.py), então uma "infração"
  é sempre vermelha e uma "conformidade" é sempre verde em qualquer tela.
- QScrollBar, QToolTip, seleção de tabela e placeholder de input estilizados
  (antes usavam o padrão feio do sistema operacional).
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

_COMMON_STRUCTURE = """
QToolTip {
    background-color: #1a1d24;
    color: #e8e9ec;
    border: 1px solid #2c2f3a;
    border-radius: 6px;
    padding: 6px 8px;
    font-size: 12px;
}

QPushButton {
    border: none;
    border-radius: 8px;
    padding: 9px 18px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton:disabled { color: #8a8d99; }

QPushButton#dangerButton:hover { background-color: #b91c1c; }
QPushButton#dangerButton:pressed { background-color: #991b1b; }

QCheckBox {
    spacing: 8px;
    padding: 4px 0;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 5px;
}

QTableWidget {
    border-radius: 10px;
    outline: none;
}
QTableWidget::item {
    padding: 6px;
    border: none;
}
QHeaderView::section {
    padding: 10px 8px;
    border: none;
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.4px;
}

QScrollBar:vertical {
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QScrollBar:horizontal {
    height: 10px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    border-radius: 5px;
    min-width: 30px;
}

QGroupBox {
    border-radius: 10px;
    margin-top: 14px;
    padding: 16px 14px 14px 14px;
    font-weight: 700;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
"""

DARK_QSS = _COMMON_STRUCTURE + """
QWidget {
    background-color: #14161c;
    color: #e8e9ec;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QMainWindow, #sidebar { background-color: #0e1015; }
#sidebar { border-right: 1px solid #23262f; }

#sidebarButton {
    text-align: left;
    padding: 11px 14px;
    border: none;
    border-radius: 8px;
    background-color: transparent;
    color: #b5b8c2;
    font-size: 13px;
    font-weight: 500;
}
#sidebarButton:hover { background-color: #1d2128; color: #ffffff; }
#sidebarButton:checked { background-color: #2563eb; color: #ffffff; font-weight: 700; }

#topBar { background-color: #14161c; border-bottom: 1px solid #23262f; }

QPushButton { background-color: #2563eb; color: white; }
QPushButton:hover { background-color: #1d4fd8; }
QPushButton:pressed { background-color: #1741b0; }
QPushButton:disabled { background-color: #262a33; }
QPushButton#dangerButton { background-color: #dc2626; }
QPushButton#secondaryButton { background-color: #23262f; color: #e8e9ec; }
QPushButton#secondaryButton:hover { background-color: #2d313c; }
QPushButton#ghostButton { background-color: transparent; color: #b5b8c2; border: 1px solid #2c2f3a; }
QPushButton#ghostButton:hover { background-color: #1d2128; color: #ffffff; }
QPushButton#iconButton { background-color: transparent; color: #b5b8c2; border-radius: 18px; padding: 6px; }
QPushButton#iconButton:hover { background-color: #23262f; }

QLineEdit, QComboBox, QSpinBox, QTextEdit, QDateEdit {
    background-color: #1c1f27;
    border: 1px solid #2c2f3a;
    border-radius: 8px;
    padding: 9px 10px;
    color: #e8e9ec;
    selection-background-color: #2563eb;
}
QLineEdit:hover, QComboBox:hover { border: 1px solid #3a3e4a; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #2563eb; }
QLineEdit::placeholder { color: #6b6f7a; }
QComboBox::drop-down { border: none; width: 24px; }
QCheckBox::indicator { background-color: #1c1f27; border: 1px solid #2c2f3a; }
QCheckBox::indicator:checked { background-color: #2563eb; border: 1px solid #2563eb; }

#card { background-color: #1a1d24; border: 1px solid #24272f; border-radius: 12px; }
#cardTitle { color: #9498a3; font-size: 11px; font-weight: 700; letter-spacing: 0.4px; }
#cardValue { color: #ffffff; font-size: 26px; font-weight: 800; }
#cardAccentDanger { border-left: 3px solid #dc2626; }
#cardAccentSuccess { border-left: 3px solid #16a34a; }
#cardAccentInfo { border-left: 3px solid #2563eb; }

QGroupBox {
    background-color: #1a1d24;
    border: 1px solid #24272f;
    color: #e8e9ec;
}

QTableWidget {
    background-color: #1a1d24;
    alternate-background-color: #1e2129;
    gridline-color: transparent;
    border: 1px solid #24272f;
    selection-background-color: #24304d;
    selection-color: #ffffff;
}
QHeaderView::section { background-color: #14161c; color: #9498a3; border-bottom: 1px solid #24272f; }
QTableWidget::item:hover { background-color: #20232b; }

QScrollBar:vertical, QScrollBar:horizontal { background: #14161c; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal { background: #2c2f3a; }
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { background: #3a3e4a; }

#statusOnline { color: #34d399; font-weight: 700; }
#statusOffline { color: #f87171; font-weight: 700; }
#statusReconnecting { color: #fbbf24; font-weight: 700; }

#cameraOverlay { background-color: rgba(10, 11, 15, 210); border-radius: 8px; }
#emptyStateFrame { background-color: transparent; }
#avatarCircle { background-color: #2563eb; color: white; border-radius: 16px; font-weight: 700; }
#notificationBadge { background-color: #dc2626; color: white; border-radius: 8px; font-size: 10px; font-weight: 700; }
"""

LIGHT_QSS = _COMMON_STRUCTURE + """
QWidget {
    background-color: #f5f6f8;
    color: #1a1c22;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QMainWindow, #sidebar { background-color: #ffffff; }
#sidebar { border-right: 1px solid #e4e6eb; }

#sidebarButton {
    text-align: left; padding: 11px 14px; border: none; border-radius: 8px;
    background-color: transparent; color: #4b4f5a; font-size: 13px; font-weight: 500;
}
#sidebarButton:hover { background-color: #eef1f6; color: #111; }
#sidebarButton:checked { background-color: #2563eb; color: #ffffff; font-weight: 700; }

#topBar { background-color: #ffffff; border-bottom: 1px solid #e4e6eb; }

QPushButton { background-color: #2563eb; color: white; }
QPushButton:hover { background-color: #1d4fd8; }
QPushButton:pressed { background-color: #1741b0; }
QPushButton:disabled { background-color: #e4e6eb; color: #9aa0ab; }
QPushButton#dangerButton { background-color: #dc2626; }
QPushButton#secondaryButton { background-color: #eef1f6; color: #1a1c22; }
QPushButton#secondaryButton:hover { background-color: #e2e5eb; }
QPushButton#ghostButton { background-color: transparent; color: #4b4f5a; border: 1px solid #d7dbe3; }
QPushButton#ghostButton:hover { background-color: #eef1f6; }
QPushButton#iconButton { background-color: transparent; color: #4b4f5a; border-radius: 18px; padding: 6px; }
QPushButton#iconButton:hover { background-color: #eef1f6; }

QLineEdit, QComboBox, QSpinBox, QTextEdit, QDateEdit {
    background-color: #ffffff; border: 1px solid #d7dbe3; border-radius: 8px;
    padding: 9px 10px; selection-background-color: #2563eb; selection-color: white;
}
QLineEdit:hover, QComboBox:hover { border: 1px solid #b7bcc7; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #2563eb; }
QCheckBox::indicator { background-color: #ffffff; border: 1px solid #d7dbe3; }
QCheckBox::indicator:checked { background-color: #2563eb; border: 1px solid #2563eb; }

#card { background-color: #ffffff; border: 1px solid #e4e6eb; border-radius: 12px; }
#cardTitle { color: #6b7280; font-size: 11px; font-weight: 700; letter-spacing: 0.4px; }
#cardValue { color: #111827; font-size: 26px; font-weight: 800; }
#cardAccentDanger { border-left: 3px solid #dc2626; }
#cardAccentSuccess { border-left: 3px solid #16a34a; }
#cardAccentInfo { border-left: 3px solid #2563eb; }

QGroupBox { background-color: #ffffff; border: 1px solid #e4e6eb; color: #1a1c22; }

QTableWidget {
    background-color: #ffffff; alternate-background-color: #f8f9fb;
    gridline-color: transparent; border: 1px solid #e4e6eb;
    selection-background-color: #dbe6fd; selection-color: #111827;
}
QHeaderView::section { background-color: #f5f6f8; color: #4b4f5a; border-bottom: 1px solid #e4e6eb; }
QTableWidget::item:hover { background-color: #f2f4f8; }

QScrollBar:vertical, QScrollBar:horizontal { background: #f5f6f8; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal { background: #d7dbe3; }
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { background: #b7bcc7; }

#statusOnline { color: #059669; font-weight: 700; }
#statusOffline { color: #dc2626; font-weight: 700; }
#statusReconnecting { color: #d97706; font-weight: 700; }

#cameraOverlay { background-color: rgba(255, 255, 255, 225); border-radius: 8px; }
#avatarCircle { background-color: #2563eb; color: white; border-radius: 16px; font-weight: 700; }
#notificationBadge { background-color: #dc2626; color: white; border-radius: 8px; font-size: 10px; font-weight: 700; }
"""


def apply_theme(app: QApplication, tema: str = "dark") -> None:
    """Aplica o QSS correspondente ao tema ('dark' ou 'light') na aplicação inteira."""
    app.setStyleSheet(DARK_QSS if tema == "dark" else LIGHT_QSS)