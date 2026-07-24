import time
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from ui.widgets.camera_widget import CameraWidget


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_camera_widget_fps_limiter(qapp):
    """Verifica se o CameraWidget respeita o limite de FPS e evita renders excessivos."""
    widget = CameraWidget(camera_id=1, nome="Cam Teste", max_ui_fps=5)
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Executa o método de atualização 10 vezes em sequência rápida (< 10ms)
    t0 = time.time()
    for _ in range(10):
        widget.atualizar_frame(fake_frame)

    # Devido ao limite de 5 FPS (intervalo de 200ms), o timestamp do último render deve ter sido registrado
    assert widget._ultimo_render_ts > 0
    assert (time.time() - t0) < 0.1
