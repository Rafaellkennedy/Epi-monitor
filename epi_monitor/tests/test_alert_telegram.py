import pytest
from unittest.mock import patch, MagicMock
from services.alert_service import AlertService

@patch("urllib.request.urlopen")
@patch("services.alert_service.settings")
def test_enviar_telegram_mock(mock_settings, mock_urlopen):
    # Simula as configurações do alert sem tentar modificar o dataclass congelado
    mock_settings.alert.telegram_bot_token = "fake_token"
    mock_settings.alert.telegram_chat_id = "12345"
    
    mock_urlopen.return_value.__enter__.return_value.status = 200
    alert_service = AlertService()
    
    # Testa chamada sem estourar exceção (apenas texto, pois snapshot=None)
    alert_service.enviar_telegram("Teste Infração", snapshot_path=None)
    assert mock_urlopen.called
