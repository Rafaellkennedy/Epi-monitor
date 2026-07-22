"""
ui/pipeline_bridge.py
------------------------
PROBLEMA: o `DetectionPipeline` roda em threads de background (pool de
inferência). É proibido atualizar widgets Qt diretamente a partir de
outra thread que não a thread principal da UI — isso causa crashes
aleatórios e comportamento indefinido.

SOLUÇÃO: esta classe é um `QObject` com sinais Qt. Sinais podem ser
emitidos de qualquer thread com segurança; o Qt garante que os slots
conectados (que atualizam a UI) rodem na thread principal (conexão
`Qt.QueuedConnection`, padrão quando emissor e receptor estão em
threads diferentes).

Uso:
    bridge = PipelineBridge()
    pipeline.registrar_callback_frame(bridge.emitir_frame)   # thread de bg
    bridge.frame_processado.connect(camera_widget.atualizar_frame)  # UI thread
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class PipelineBridge(QObject):
    # (camera_id, resultado_analise)
    frame_processado = Signal(int, object)
    # (camera_id, status)
    status_alterado = Signal(int, object)
    # (dict com dados do alerta: camera, mensagem, severidade...)
    alerta_disparado = Signal(dict)

    def emitir_frame(self, camera_id: int, resultado) -> None:
        """Callback registrado no pipeline; chamado a partir de thread de background."""
        self.frame_processado.emit(camera_id, resultado)

    def emitir_status(self, camera_id: int, status) -> None:
        self.status_alterado.emit(camera_id, status)

    def emitir_alerta(self, dados_alerta: dict) -> None:
        self.alerta_disparado.emit(dados_alerta)
