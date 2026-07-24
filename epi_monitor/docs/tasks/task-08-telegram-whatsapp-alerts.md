# Task 08: Integração Completa de Canais de Alerta (Telegram e WhatsApp)

## 📌 Informações da Task & Git Flow

- **ID:** TASK-08
- **Título:** Notificações em Tempo Real via Telegram Bot API e WhatsApp API
- **Branch Recomendada:** `feature/telegram-whatsapp-alerts`
- **Base Branch:** `main` ou `develop`
- **Arquivos Afetados:**
  - [services/alert_service.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/services/alert_service.py)
  - [config/settings.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/config/settings.py)

---

## 🔴 1. O que está errado (Diagnóstico do Problema)

### Sintoma
Os técnicos de segurança que estão em campo não recebem alertas em seus celulares. As funções para Telegram e WhatsApp emitem exceção `NotImplementedError`.

### Causa Raiz
No arquivo [alert_service.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/services/alert_service.py#L175-L190), os métodos de envio foram deixados com marcadores `TODO`:

```python
# CÓDIGO ATUAL COM DEFEITO (alert_service.py)
def enviar_telegram(self, mensagem: str, snapshot_path: Optional[str] = None) -> None:
    raise NotImplementedError("Integração com Telegram ainda não implementada.")
```

---

## 🟢 2. Caminho para a Solução (Guia de Refatoração)

### Estratégia de Refatoração:
1. **Integração com Telegram Bot API**: Utilizar `urllib.request` ou `requests` para enviar uma requisição HTTP `POST` para `https://api.telegram.org/bot<TOKEN>/sendPhoto` contendo o texto da mensagem e o arquivo JPEG anexado.
2. **Integração com WhatsApp Webhook/API**: Implementar a chamada HTTP `POST` para o endpoint configurado (`settings.alert.whatsapp_api_url`) enviando o payload JSON com o número de destino e o link/imagem base64 da evidência.
3. **Execução Assíncrona em Background**: Garantir que o envio rode em uma thread separada (`daemon=True`) para não bloquear a detecção de vídeo caso a conexão de internet oscile.

### Passo a Passo de Código:

#### Alteração em [`services/alert_service.py`](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/services/alert_service.py)
```python
import urllib.request
import urllib.parse
from pathlib import Path

class AlertService:
    # ...
    def enviar_telegram_async(self, mensagem: str, snapshot_path: str | None = None) -> None:
        t = threading.Thread(target=self.enviar_telegram, args=(mensagem, snapshot_path), daemon=True)
        t.start()

    def enviar_telegram(self, mensagem: str, snapshot_path: str | None = None) -> None:
        token = settings.alert.telegram_bot_token
        chat_id = settings.alert.telegram_chat_id

        if not token or not chat_id:
            logger.warning("Telegram Bot Token ou Chat ID não configurados.")
            return

        try:
            if snapshot_path and Path(snapshot_path).exists():
                url = f"https://api.telegram.org/bot{token}/sendPhoto"
                # Monta multipart/form-data via urllib para upload da imagem JPEG
                boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
                data = []
                data.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{chat_id}\r\n".encode())
                data.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{mensagem}\r\n".encode())
                
                with open(snapshot_path, "rb") as f:
                    filename = Path(snapshot_path).name
                    data.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"{filename}\"\r\nContent-Type: image/jpeg\r\n\r\n".encode())
                    data.append(f.read())
                    data.append(b"\r\n")
                
                data.append(f"--{boundary}--\r\n".encode())
                body = b"".join(data)

                req = urllib.request.Request(url, data=body)
                req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    logger.info(f"Notificação Telegram enviada com sucesso: {resp.status}")
        except Exception as e:
            logger.error(f"Falha ao enviar mensagem via Telegram: {e}")
```

---

## 🧪 3. Plano de Testes (Antes de Fazer Merge)

### A. Teste Unitário com Mock (`tests/test_alert_telegram.py`)
```python
import pytest
from unittest.mock import patch
from services.alert_service import AlertService

@patch("urllib.request.urlopen")
def test_enviar_telegram_mock(mock_urlopen):
    mock_urlopen.return_value.__enter__.return_value.status = 200
    alert_service = AlertService()
    
    # Testa chamada sem estourar exceção
    alert_service.enviar_telegram("Teste Infração", snapshot_path=None)
```

---

## 🔀 4. Git Flow & Checklist de Pull Request (PR)

### Comandos Git para abrir a Branch:
```bash
git checkout main
git pull origin main
git checkout -b feature/telegram-whatsapp-alerts
```

### Mensagem de Commit Padronizada:
`feat(alert): implement Telegram Bot API notification dispatch with photo attachment`

### Critérios para Aprovação do PR:
- [ ] Teste unitário com mock aprovado.
- [ ] Recebimento confirmado de mensagem e imagem de snapshot no Telegram de teste.
