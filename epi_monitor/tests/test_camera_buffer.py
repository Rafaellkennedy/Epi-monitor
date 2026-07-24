import pytest
import numpy as np
from services.camera_service import CameraStream, CameraConfig


def test_pre_buffer_ram_compression():
    """Testa se o pre-buffer armazena frames comprimidos em bytes JPEG, economizando RAM."""
    config = CameraConfig(id=1, nome="Test Cam", url_rtsp="rtsp://dummy", fps_alvo=10)
    stream = CameraStream(config)

    # Simula 50 frames Full HD (1920x1080)
    fake_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    for _ in range(50):
        stream._atualizar_pre_buffer(fake_frame)

    # 1. Verifica se guardou 50 frames no deque
    assert len(stream._pre_buffer) == 50

    # 2. Verifica tamanho total em memória (bytes JPEG)
    tamanho_total_bytes = sum(len(jpg_bytes) for _, jpg_bytes in stream._pre_buffer)
    tamanho_total_mb = tamanho_total_bytes / (1024 * 1024)

    # 50 frames Full HD cru teriam ~310 MB. Comprimidos em JPEG sintético devem ocupar < 2 MB.
    assert tamanho_total_mb < 5.0, f"Buffer ocupando {tamanho_total_mb:.2f} MB, esperava < 5.0 MB"

    # 3. Testa se a decodificação recupera os quadros corretamente
    frames_recuperados = stream.get_pre_buffer()
    assert len(frames_recuperados) == 50
    assert frames_recuperados[0].shape == (1080, 1920, 3)
