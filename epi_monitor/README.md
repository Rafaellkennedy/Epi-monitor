# EPI Monitor — Sistema de Monitoramento de EPIs por IA (CFTV)

Sistema profissional de monitoramento de câmeras de segurança (CFTV) com
detecção automática de uso de Equipamentos de Proteção Individual (EPIs)
usando visão computacional (YOLOv11), construído em Clean Architecture.

---

## 1. Arquitetura do Projeto

```
epi_monitor/
├── app/
│   └── main.py              # Ponto de entrada da aplicação
├── config/
│   └── settings.py          # Configurações centralizadas (lê .env)
├── core/
│   └── security.py          # Autenticação, hashing de senha, RBAC
├── models/
│   ├── enums.py              # Enums de domínio (NivelAcesso, TipoEPI...)
│   └── detection.py         # DTOs de detecção (Detection, ResultadoAnalise...)
├── database/
│   ├── models.py             # Entidades ORM (SQLAlchemy) = tabelas do banco
│   ├── connection.py        # Engine/Session do PostgreSQL
│   └── seed.py               # Dados iniciais (usuário admin, configs)
├── detection/
│   ├── yolo_detector.py     # Wrapper do modelo YOLOv11 (Ultralytics)
│   └── epi_checker.py       # Associa EPIs detectados às pessoas e verifica conformidade
├── services/
│   ├── camera_service.py     # Captura RTSP em thread (CameraStream/CameraManager)
│   ├── camera_repository.py # CRUD de câmeras no banco
│   ├── onvif_service.py     # Descoberta ONVIF e obtenção de URI RTSP
│   ├── detection_pipeline.py # Orquestra captura + inferência + alertas (múltiplas câmeras)
│   ├── recording_service.py # Salva snapshots e clipes de vídeo das infrações
│   ├── event_service.py     # Persistência/consulta de eventos + estatísticas
│   └── alert_service.py     # Alarme sonoro, e-mail, cooldown, pontos de extensão
├── ui/
│   ├── main_window.py        # Janela principal (sidebar + páginas)
│   ├── login_window.py       # Tela de login
│   ├── theme.py               # QSS dos temas claro/escuro
│   ├── pipeline_bridge.py    # Ponte thread-safe entre pipeline (bg) e Qt (UI thread)
│   ├── widgets/
│   │   └── camera_widget.py  # Card de vídeo individual de câmera
│   └── pages/
│       ├── dashboard_page.py
│       ├── cameras_page.py
│       ├── events_page.py
│       └── settings_page.py
├── utils/
│   └── logger.py              # Configuração central de logging
├── installer/
│   ├── epi_monitor.spec      # Build PyInstaller (.exe)
│   ├── setup_inno.iss         # Instalador Windows (Inno Setup)
│   └── auto_updater.py       # Verificação/aplicação de atualizações
├── scripts/
│   └── setup_database.py     # Cria banco + tabelas + dados iniciais
├── resources/
│   ├── sounds/                # Som de alarme (alarme.wav)
│   ├── icons/                 # Ícone do app (.ico)
│   └── models/                # Modelo YOLO treinado (epi_best.pt) — NÃO incluso
├── requirements.txt
├── .env.example
└── version.txt
```

**Camadas (Clean Architecture):**
- `models/` e `database/models.py` — entidades de domínio, sem dependência de framework.
- `core/`, `detection/`, `services/` — regras de negócio e infraestrutura (banco, câmeras, IA).
- `ui/` — camada de apresentação (PySide6), depende dos serviços, nunca o contrário.
- `config/` — configuração cross-cutting, injetada via `settings` singleton.

---

## 2. Instalação (ambiente de desenvolvimento)

### Pré-requisitos
- Python 3.13
- PostgreSQL 14+ instalado e em execução
- FFmpeg instalado e no PATH do sistema
- (Opcional, recomendado) GPU NVIDIA com driver CUDA para melhor desempenho

### Passos

```bash
# 1. Criar ambiente virtual
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Configurar variáveis de ambiente
copy .env.example .env         # Windows
# cp .env.example .env         # Linux/Mac
# edite o .env com as credenciais do seu PostgreSQL

# 4. Criar banco de dados + tabelas + usuário admin
python scripts/setup_database.py

# 5. Executar a aplicação
python -m app.main
```

**Login padrão:** `admin` / `admin123` — altere a senha após o primeiro acesso.

---

## 3. Modelo de Detecção (YOLOv11) — PASSO CRÍTICO

O código em `detection/yolo_detector.py` usa um modelo em
`resources/models/epi_best.pt`, que **não está incluído** neste projeto
(modelos treinados são específicos do ambiente/EPIs da empresa e pesados
demais para versionar como código-fonte).

### Como obter o modelo:

**Opção A — Treinar um modelo customizado (recomendado para produção):**
1. Colete/anote um dataset de imagens do ambiente da empresa (ou use bases
   públicas como "Construction Site Safety" / "Hard Hat Workers" no
   Roboflow Universe) com as classes: `capacete`, `sem_capacete`, `oculos`,
   `sem_oculos`, `colete`, `sem_colete`, `mascara`, `sem_mascara`, `luvas`,
   `sem_luvas`, `pessoa`.
2. Treine com Ultralytics:
   ```bash
   yolo detect train data=epi_dataset.yaml model=yolo11n.pt epochs=100 imgsz=640
   ```
3. Copie o `best.pt` resultante para `resources/models/epi_best.pt`.

**Opção B — Uso demonstrativo/dev:** se o arquivo não existir, o sistema
faz fallback automático para `yolo11n.pt` (modelo genérico do Ultralytics,
baixado automaticamente), que detecta apenas a classe `person` — útil para
testar a pipeline de câmeras/UI, mas **não detecta EPIs** até que o modelo
customizado seja fornecido.

---

## 4. Geração do instalador Windows (.exe)

```bash
cd installer
pyinstaller epi_monitor.spec
# Saída em: installer/dist/EPIMonitor/EPIMonitor.exe

# Gerar o instalador com Inno Setup (após instalar o Inno Setup):
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" setup_inno.iss
# Saída em: installer/output/EPIMonitor_Setup_1.0.0.exe
```

O PostgreSQL **não** é empacotado pelo instalador — deve ser instalado
separadamente no computador/servidor que ficará conectado à central de
câmeras (ver comentário no final de `setup_inno.iss` para embutir um
PostgreSQL portátil, se desejado).

---

## 5. Integrações futuras (Telegram / WhatsApp)

Os métodos `AlertService.enviar_telegram()` e `AlertService.enviar_whatsapp()`
em `services/alert_service.py` já têm assinatura pronta e estão documentados
com `TODO`. Para ativá-los:
- **Telegram:** criar um bot via `@BotFather`, preencher `TELEGRAM_BOT_TOKEN`
  e `TELEGRAM_CHAT_ID` no `.env`, e implementar a chamada HTTP à API
  `sendPhoto`/`sendMessage` do Telegram Bot API.
- **WhatsApp:** integrar via WhatsApp Business API oficial ou um provedor
  terceirizado (Twilio, Z-API, etc.), preenchendo `WHATSAPP_API_URL` e
  `WHATSAPP_API_TOKEN`.

---

## 6. O que este projeto entrega vs. o que exige trabalho adicional

**Entregue e funcional:**
- Arquitetura completa em Clean Architecture, todas as camadas conectadas.
- Banco PostgreSQL com todas as tabelas especificadas (usuários, câmeras,
  eventos, alertas, configurações, logs) via SQLAlchemy.
- Autenticação com bcrypt, bloqueio por tentativas, 3 níveis de acesso.
- Captura RTSP multi-câmera em threads, com reconexão automática.
- Pipeline de detecção YOLO + verificação de EPI por pessoa, com desenho
  de caixas e % de confiança.
- Registro de eventos, snapshot e gravação de clipe de vídeo de 10s.
- Alerta sonoro + e-mail, com cooldown configurável.
- Interface completa: login, dashboard, grid de câmeras ao vivo, cadastro
  de câmeras/EPIs, histórico de eventos com evidências, configurações,
  tema claro/escuro.
- Especificação de build PyInstaller + instalador Inno Setup + esqueleto
  de auto-atualizador.

**Requer trabalho/ajuste antes de produção:**
- **Treinar o modelo YOLO customizado** de EPIs (item mais crítico —
  ver seção 3). Sem isso, a detecção de EPIs não funciona de verdade.
- Testes de carga reais com até 50 câmeras simultâneas para calibrar
  `frame_skip`, `max_workers_inferencia` e hardware necessário (GPU).
- Tela de gestão de usuários (CRUD) na UI — o modelo/serviço de dados já
  existe (`Usuario`, `AuthService`); falta só a página Qt de administração,
  seguindo o mesmo padrão das páginas já implementadas.
- Migrações versionadas com Alembic (atualmente o schema é criado via
  `create_all`, adequado para deploy inicial, não para evoluções futuras
  do schema em produção).
- Assinatura de código do `.exe` (code signing) para evitar alertas do
  SmartScreen do Windows.
- Testes automatizados (unitários e de integração).

---

## 7. Suporte a GPU

O sistema detecta automaticamente GPU NVIDIA disponível
(`config/settings.py` → `YOLO_DEVICE=auto`, resolvido em
`detection/yolo_detector.py`). Para forçar CPU (ex.: testes), defina
`YOLO_DEVICE=cpu` no `.env`.
