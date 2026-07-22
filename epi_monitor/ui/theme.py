"""
ui/theme.py
-----------
Define os temas visuais (dark/light) da aplicação via QSS (Qt Style Sheets,
sintaxe muito parecida com CSS). Centralizar aqui permite alternar o tema
inteiro da aplicação com uma única chamada de `apply_theme()`.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

# Paleta de cores - tema escuro (padrão para monitoramento, reduz fadiga visual)
DARK_QSS = """
QWidget {
    background-color: #14161c;
    color: #e8e9ec;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QMainWindow, #sidebar {
    background-color: #0e1015;
}
#sidebar {
    border-right: 1px solid #23262f;
}
#sidebarButton {
    text-align: left;
    padding: 12px 16px;
    border: none;
    border-radius: 8px;
    background-color: transparent;
    color: #b5b8c2;
    font-size: 14px;
}
#sidebarButton:hover {
    background-color: #1d2128;
    color: #ffffff;
}
#sidebarButton:checked {
    background-color: #2563eb;
    color: #ffffff;
    font-weight: 600;
}
#topBar {
    background-color: #14161c;
    border-bottom: 1px solid #23262f;
}
QPushButton {
    background-color: #2563eb;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}
QPushButton:hover { background-color: #1d4fd8; }
QPushButton:disabled { background-color: #3a3d47; color: #8a8d99; }
QPushButton#dangerButton { background-color: #dc2626; }
QPushButton#dangerButton:hover { background-color: #b91c1c; }
QPushButton#secondaryButton { background-color: #2a2d36; color: #e8e9ec; }
QPushButton#secondaryButton:hover { background-color: #363a45; }

QLineEdit, QComboBox, QSpinBox, QTextEdit, QDateEdit {
    background-color: #1c1f27;
    border: 1px solid #2c2f3a;
    border-radius: 6px;
    padding: 8px;
    color: #e8e9ec;
}
QLineEdit:focus, QComboBox:focus { border: 1px solid #2563eb; }

#card {
    background-color: #1a1d24;
    border: 1px solid #24272f;
    border-radius: 12px;
}
#cardTitle { color: #9498a3; font-size: 12px; font-weight: 600; }
#cardValue { color: #ffffff; font-size: 26px; font-weight: 700; }

QTableWidget {
    background-color: #1a1d24;
    alternate-background-color: #1e2129;
    gridline-color: #262a33;
    border: 1px solid #262a33;
    border-radius: 8px;
}
QHeaderView::section {
    background-color: #14161c;
    color: #b5b8c2;
    padding: 8px;
    border: none;
    font-weight: 600;
}
QScrollBar:vertical { background: #14161c; width: 10px; }
QScrollBar::handle:vertical { background: #2c2f3a; border-radius: 5px; }

#statusOnline { color: #34d399; font-weight: 600; }
#statusOffline { color: #f87171; font-weight: 600; }
#statusReconnecting { color: #fbbf24; font-weight: 600; }
"""

# Paleta de cores - tema claro
LIGHT_QSS = """
QWidget {
    background-color: #f5f6f8;
    color: #1a1c22;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QMainWindow, #sidebar { background-color: #ffffff; }
#sidebar { border-right: 1px solid #e4e6eb; }
#sidebarButton {
    text-align: left; padding: 12px 16px; border: none; border-radius: 8px;
    background-color: transparent; color: #4b4f5a; font-size: 14px;
}
#sidebarButton:hover { background-color: #eef1f6; color: #111; }
#sidebarButton:checked { background-color: #2563eb; color: #ffffff; font-weight: 600; }
#topBar { background-color: #ffffff; border-bottom: 1px solid #e4e6eb; }
QPushButton {
    background-color: #2563eb; color: white; border: none; border-radius: 6px;
    padding: 8px 16px; font-weight: 600;
}
QPushButton:hover { background-color: #1d4fd8; }
QPushButton#dangerButton { background-color: #dc2626; }
QPushButton#secondaryButton { background-color: #eef1f6; color: #1a1c22; }
QLineEdit, QComboBox, QSpinBox, QTextEdit, QDateEdit {
    background-color: #ffffff; border: 1px solid #d7dbe3; border-radius: 6px; padding: 8px;
}
#card { background-color: #ffffff; border: 1px solid #e4e6eb; border-radius: 12px; }
#cardTitle { color: #6b7280; font-size: 12px; font-weight: 600; }
#cardValue { color: #111827; font-size: 26px; font-weight: 700; }
QTableWidget {
    background-color: #ffffff; alternate-background-color: #f8f9fb;
    gridline-color: #e4e6eb; border: 1px solid #e4e6eb; border-radius: 8px;
}
QHeaderView::section { background-color: #f5f6f8; color: #4b4f5a; padding: 8px; border: none; font-weight: 600; }
#statusOnline { color: #059669; font-weight: 600; }
#statusOffline { color: #dc2626; font-weight: 600; }
#statusReconnecting { color: #d97706; font-weight: 600; }
"""


def apply_theme(app: QApplication, tema: str = "dark") -> None:
    """Aplica o QSS correspondente ao tema ('dark' ou 'light') na aplicação inteira."""
    app.setStyleSheet(DARK_QSS if tema == "dark" else LIGHT_QSS)
