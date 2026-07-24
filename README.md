# 🛡️ EPI Monitor — Sistema Inteligente de Monitoramento de EPIs (CFTV & IA)

[![Python Version](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/GUI-PySide6%20%2F%20Qt-green.svg)](https://doc.qt.io/qtforpython-6/)
[![AI Vision](https://img.shields.io/badge/YOLO-v11%20(Ultralytics)-orange.svg)](https://docs.ultralytics.com/)
[![Database](https://img.shields.io/badge/PostgreSQL-15%2B-blue.svg)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Supported-blue.svg)](https://www.docker.com/)

O **EPI Monitor** é uma solução profissional para monitoramento de segurança do trabalho em usinas, fábricas e canteiros de obras. Utilizando visão computacional em tempo real sobre fluxos de vídeo CFTV (câmeras IP via RTSP/ONVIF), o sistema identifica automaticamente a conformidade ou infração no uso de **Equipamentos de Proteção Individual (EPIs)** como capacetes, óculos de proteção, coletes reflexivos, máscaras e luvas.

---

## 📅 Estágio Atual do Projeto

**Última Atualização:** 24 de Julho de 2026  
**Status Atual:** 🟢 *Em Desenvolvimento Ativo / Refatoração de Alta Performance e Conteinerização*

### 🛠️ O que já foi concluído e validado:
- [x] **Arquitetura Base**: Implementação em **Clean Architecture** segregando UI, Serviços, Detecção e Persistência.
- [x] **Segurança e RBAC**: Criptografia de senhas com `bcrypt` (salt único), controle de bloqueio temporário e 3 níveis de permissão (Administrador, Técnico de Segurança, Operador).
- [x] **TASK-01 (Otimização de RAM no Pre-Buffer)**: Refatoração da retenção de vídeos pré-evento para uso de buffer JPEG comprimido em memória e `collections.deque` com limite de quadros. Redução de mais de **90% do consumo de memória RAM** (~310 MB para <5 MB por câmera). Teste unitário aprovado com 100% de sucesso.
- [x] **TASK-09 (Conteinerização Docker & Docker Compose)**: Implementação de `Dockerfile` otimizado (download do PyTorch CPU via repositório oficial para prevenir timeouts) e `docker-compose.yml` para subida unificada do banco PostgreSQL 15 e da aplicação EPI Monitor com auto-seed.

### 📋 Próximas Etapas no Roadmap:
- [ ] **TASK-02**: Fila de inferência assíncrona e lote (`Batch Inference` na GPU).
- [ ] **TASK-03**: Limitador de FPS de exibição visual no `CameraWidget` (prevenção de UI Lag).
- [ ] **TASK-04**: Object Tracking com **ByteTrack** e filtro de persistência temporal (debounce de 3 a 5 quadros).
- [ ] **TASK-05**: Configuração do **Alembic** para migrações e criação de índices SQL compostos na tabela de eventos.
- [ ] **TASK-06**: Interface Gráfica para Gestão e CRUD de Usuários (`UsersPage`).
- [ ] **TASK-07**: Filtragem de detecções por Polígono de Área de Risco (ROI).
- [ ] **TASK-08**: Notificações automáticas via Telegram Bot API e WhatsApp API.

---

## 🏗️ Arquitetura & System Design

O sistema adota os princípios de **Clean Architecture** (Arquitetura Limpa), visando o desacoplamento entre as regras de negócio, a camada de visão computacional, a interface gráfica e o banco de dados.

```
                               ┌───────────────────────────┐
                               │  Câmeras CFTV (RTSP/ONVIF) │
                               └─────────────┬─────────────┘
                                             │ (Frames BGR)
                                             ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ CAMADA DE SERVIÇOS & CAPTURA                                                           │
│                                                                                        │
│   ┌─────────────────────┐      ┌─────────────────────────┐     ┌────────────────────┐  │
│   │    CameraStream     ├─────►│  Pre-Buffer Comprimido  ├────►│ RecordingService   │  │
│   │ (Thread Individual) │      │   (JPEG / deque maxlen) │     │ (Snapshot & Clipes)│  │
│   └──────────┬──────────┘      └─────────────────────────┘     └────────────────────┘  │
└──────────────┼─────────────────────────────────────────────────────────────────────────┘
               │ (Latest Frame)
               ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ CAMADA DE DETECÇÃO & INTELIGÊNCIA ARTIFICIAL                                           │
│                                                                                        │
│   ┌─────────────────────┐      ┌─────────────────────────┐     ┌────────────────────┐  │
│   │    YoloDetector     ├─────►│       EPIChecker        ├────►│  ResultadoAnalise  │  │
│   │ (YOLOv11 / PyTorch) │      │ (Associação BBox/EPI)   │     │  (DTO de Domínio)  │  │
│   └─────────────────────┘      └─────────────────────────┘     └─────────┬──────────┘  │
└────────────────────────────────────────────────────────────────────────────────────────┘
                                                                           │
                                                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ CAMADA DE APRESENTAÇÃO & BANCO DE DADOS                                                │
│                                                                                        │
│   ┌─────────────────────┐      ┌─────────────────────────┐     ┌────────────────────┐  │
│   │   PipelineBridge    ├─────►│  PySide6 (Qt) UI Thread │     │ PostgreSQL Database│  │
│   │   (QObject Signals) │      │ (Main Window / Grid)    │     │  (SQLAlchemy 2.0)  │  │
│   └─────────────────────┘      └─────────────────────────┘     └────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Componentes Principais:
1. **`CameraStream`** (`services/camera_service.py`): Mantém a conexão RTSP em thread dedicada por câmera, capturando quadros e armazenando os últimos 5 segundos em um buffer circular leve de bytes JPEG comprimidos.
2. **`YoloDetector`** (`detection/yolo_detector.py`): Encapsula o modelo **YOLOv11** (Ultralytics) para localização das caixas delimitadoras (bounding boxes) e identificação das classes.
3. **`EPIChecker`** (`detection/epi_checker.py`): Executa a regra de negócio espacial, verificando para cada pessoa quais EPIs obrigatorios cadastrados para aquela câmera estão presentes ou ausentes.
4. **`PipelineBridge`** (`ui/pipeline_bridge.py`): Canal de comunicação thread-safe baseado em `QObject` e `Signals` do Qt, permitindo que as threads de inferência enviem atualizações de tela para a UI sem provocar crashes ou congelamento.
5. **`AlertService` & `EventService`**: Registram auditorias de infração no PostgreSQL e disparam alertas sonoros, e-mails e evidencias.

---

### 🗄️ Esquema do Banco de Dados (Diagrama de Entidade-Relacionamento - ER)

```mermaid
erDiagram
    usuarios ||--o{ alertas : "reconhece"
    usuarios ||--o{ logs : "gera"
    cameras ||--o{ camera_epis : "exige"
    cameras ||--o{ eventos : "registra"
    eventos ||--o{ alertas : "gera"

    usuarios {
        int id PK
        string nome_completo
        string login UK
        string email
        string senha_hash
        enum nivel_acesso
        boolean ativo
        int tentativas_login_falhas
        datetime bloqueado_ate
        datetime criado_em
        datetime ultimo_login
    }

    cameras {
        int id PK
        string nome
        string localizacao
        enum protocolo
        string url_rtsp
        string onvif_host
        int onvif_port
        string onvif_usuario
        string onvif_senha
        boolean ativa
        enum status
        int fps_alvo
        text zona_deteccao_json
        datetime criado_em
        datetime atualizado_em
    }

    camera_epis {
        int id PK
        int camera_id FK
        enum tipo_epi
        boolean obrigatorio
    }

    eventos {
        int id PK
        int camera_id FK
        enum tipo_evento
        text epis_ausentes_json
        float confianca_media
        string caminho_snapshot
        string caminho_video_clip
        datetime data_hora IX
        text observacoes
    }

    alertas {
        int id PK
        int evento_id FK
        enum severidade
        enum status
        enum canal
        text mensagem
        datetime criado_em
        datetime reconhecido_em
        int reconhecido_por_id FK
    }

    configuracoes {
        int id PK
        string chave UK
        text valor
        string descricao
        datetime atualizado_em
    }

    logs {
        int id PK
        int usuario_id FK
        enum nivel
        string origem
        text mensagem
        datetime data_hora IX
    }
```

---

## 🛠️ Tecnologias e Ferramentas Utilizadas

- **Linguagem**: Python 3.12 / 3.13
- **Interface Gráfica (GUI)**: PySide6 (Qt for Python 6.7+)
- **Visão Computacional & IA**: Ultralytics YOLOv11, OpenCV 4.10, PyTorch 2.3+, NumPy
- **Banco de Dados & ORM**: PostgreSQL 15, SQLAlchemy 2.0 (Declarative Mapped Style), psycopg2
- **Segurança**: Bcrypt (Hashing com Salt automático), Python-Dotenv
- **Integração de Vídeo**: Protocolo RTSP (OpenCV FFmpeg backend), ONVIF (wsdiscovery, onvif-zeep)
- **Conteinerização & Deploy**: Docker, Docker Compose, PyInstaller, Inno Setup
- **Testes & Qualidade**: Pytest, Pytest-Qt

---

## 📂 Estrutura do Repositório

```
Epi-monitor/
├── docker-compose.yml            # Orquestração do PostgreSQL + App EPI Monitor
├── Dockerfile                    # Configuração da imagem Docker multi-stage
├── .dockerignore                 # Exclusões para context do Docker
├── .gitignore                    # Exclusões de ambiente, cache e arquivos pesados
├── README.md                     # Documentação principal do repositório
│
└── epi_monitor/                  # Pacote principal da aplicação
    ├── app/
    │   └── main.py               # Ponto de entrada da aplicação
    ├── config/
    │   └── settings.py           # Single source of truth (dataclasses + .env)
    ├── core/
    │   └── security.py           # Autenticação (bcrypt), lockout e RBAC
    ├── database/
    │   ├── connection.py         # Conexão e SessionFactory SQLAlchemy
    │   ├── models.py             # Entidades ORM (Usuario, Camera, Evento, Alerta)
    │   └── seed.py               # População de dados iniciais (admin/configurações)
    ├── detection/
    │   ├── yolo_detector.py      # Wrapper do modelo YOLOv11 (Ultralytics)
    │   └── epi_checker.py        # Lógica espacial de associação Pessoa <-> EPI
    ├── services/
    │   ├── camera_service.py     # Captura de vídeo RTSP em thread própria
    │   ├── camera_repository.py  # Persistência e CRUD de câmeras
    │   ├── detection_pipeline.py # Orquestrador da inferência multi-câmera
    │   ├── recording_service.py  # Gravação de snapshots e vídeos MP4 de infração
    │   ├── event_service.py      # Histórico de eventos e agregador de Dashboard
    │   ├── alert_service.py      # Gerenciamento de cooldown, som e notificações
    │   └── onvif_service.py      # Descoberta de câmeras via ONVIF (WS-Discovery)
    ├── ui/
    │   ├── main_window.py        # Janela principal PySide6 (Sidebar + StackedWidget)
    │   ├── login_window.py       # Tela de autenticação
    │   ├── pipeline_bridge.py    # Ponte de sinais thread-safe entre BG e Qt
    │   ├── pages/                # Telas (Dashboard, Câmeras, Eventos, Configurações)
    │   └── widgets/              # Componentes (CameraWidget de exibição de vídeo)
    ├── docs/
    │   └── tasks/                # Guias detalhados de refatoração para cada task
    └── tests/
        └── test_camera_buffer.py # Suíte de testes unitários do sistema
```

---

## 🚀 Como Rodar o Projeto

Você pode executar o **EPI Monitor** de duas maneiras: utilizando **Docker Compose** (recomendado para rápida implantação de 1 comando) ou **localmente** em ambiente virtual Python.

### Opção 1: Rodando via Docker Compose (Recomendado)

O Docker Compose sobe automaticamente o container do **PostgreSQL 15** e a aplicação **EPI Monitor**, preparando o banco de dados e populando os dados iniciais.

#### Pré-requisitos:
- [Docker](https://www.docker.com/) e Docker Compose instalados.

#### Passos:
```bash
# 1. Clone o repositório
git clone https://github.com/Rafaellkennedy/Epi-monitor.git
cd Epi-monitor

# 2. Construa a imagem e inicie os containers
docker compose up --build -d

# 3. Acompanhe os logs da aplicação e verifique a inicialização do banco
docker compose logs app -f
```

---

### Opção 2: Rodando Localmente (Desenvolvimento)

#### Pré-requisitos:
- Python 3.12 ou 3.13 instalado.
- PostgreSQL 14+ instalado e em execução na máquina.
- FFmpeg instalado e configurado no PATH do sistema.

#### Passos:

```bash
# 1. Clone o repositório e acesse a pasta da aplicação
git clone https://github.com/Rafaellkennedy/Epi-monitor.git
cd Epi-monitor/epi_monitor

# 2. Crie e ative um ambiente virtual (venv)
python -m venv venv
# Linux/Mac:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure as variáveis de ambiente
cp .env.example .env
# Edite o arquivo .env com a senha e endereço do seu PostgreSQL local

# 5. Crie o banco de dados e rode a carga inicial (seed)
python scripts/setup_database.py

# 6. Execute o sistema
python -m app.main
```

> 🔑 **Credenciais Padrão de Login**:  
> **Usuário**: `admin`  
> **Senha**: `admin123`  
> *(Altere a senha após o primeiro acesso no ambiente de produção).*

---

## 🧪 Executando os Testes Automatizados

O projeto utiliza o **Pytest** para validação das camadas de serviço e prevenção de regressões:

```bash
cd epi_monitor
pytest tests/ -v
```

---

## 🔀 Fluxo de Contribuição e Git Flow

Todas as alterações e melhorias do projeto seguem o padrão **Git Flow com Feature Branches**:

1. Crie uma branch para a demanda a partir da `main`:
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/nome-da-feature
   ```
2. Desenvolva as alterações e execute a suíte de testes.
3. Realize o commit seguindo os padrões de [Conventional Commits](https://www.conventionalcommits.org/):
   ```bash
   git commit -m "feat(scope): mensagem clara da alteração"
   ```
4. Envie a branch e abra um **Pull Request (PR)** para a `main`.

---

## 📄 Licença

Este projeto é desenvolvido para monitoramento de segurança industrial e conformidade de EPIs. Todos os direitos reservados.
