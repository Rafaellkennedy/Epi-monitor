# Task 09: Conteinerização e Integração com Docker & Docker Compose

## 📌 Informações da Task & Git Flow

- **ID:** TASK-09
- **Título:** Conteinerização do EPI Monitor com Docker e Docker Compose (PostgreSQL + App)
- **Branch Recomendada:** `feature/docker-integration`
- **Base Branch:** `main` ou `develop`
- **Arquivos Afetados:**
  - `Dockerfile` (Novo)
  - `docker-compose.yml` (Novo)
  - `.dockerignore` (Novo)
  - `docker/entrypoint.sh` (Novo)
  - [config/settings.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/config/settings.py)

---

## 🔴 1. O que está errado (Diagnóstico do Problema)

### Sintoma
A instalação do projeto em um novo computador/servidor de usina exige a instalação manual de múltiplas dependências complexas no sistema operacional (Python 3.13, PostgreSQL 14+, FFmpeg, drivers CUDA NVIDIA, Bibliotecas C/C++ de mídia).

### Causa Raiz
O projeto não possui arquivos de conteinerização (`Dockerfile` e `docker-compose.yml`). Qualquer divergência de versão no FFmpeg ou no PostgreSQL entre o ambiente de dev e a usina pode causar falhas de conexão RTSP ou erros de driver de banco de dados.

---

## 🟢 2. Caminho para a Solução (Guia de Refatoração)

### Estratégia de Refatoração:
1. **Criar `Dockerfile` Multi-Stage (com Suporte a FFmpeg e CUDA)**:
   - Base de imagem Python 3.12/3.13 Slim ou PyTorch CUDA (`nvidia/cuda`).
   - Instalação dos pacotes de sistema necessários: `ffmpeg`, `libgl1`, `libglib2.0-0`, `libgomp1`.
   - Instalação dos pacotes do `requirements.txt`.
2. **Criar `docker-compose.yml`**:
   - Serviço `db`: Imagem oficial `postgres:15-alpine` com volume persistente `postgres_data`.
   - Serviço `app`: Imagem do EPI Monitor conectada à rede interna do Compose, com suporte a variáveis de ambiente via `.env`.
3. **Criar Script `entrypoint.sh`**:
   - Aguarda o PostgreSQL ficar pronto (`pg_isready` / `nc -z`).
   - Roda a inicialização e seed do banco (`python scripts/setup_database.py`).
   - Inicia a aplicação EPI Monitor.
4. **Configuração de Display (X11 / Forwarding ou Headless Mode)**:
   - Suporte a repassar a interface gráfica Qt via servidor X11 (`DISPLAY=${DISPLAY}`) ou executar o pipeline de monitoramento de forma autônoma (headless).

---

## 🧪 3. Plano de Testes (Antes de Fazer Merge)

### A. Teste de Subida de Containers (`docker compose up`)
```bash
# Subir o ambiente completo via Docker Compose
docker compose up --build -d

# Verificar se os containers estão rodando com status Healthy
docker compose ps
```

### B. Teste de Conectividade do Banco e Seed
```bash
# Verificar logs da aplicação no Docker
docker compose logs app
```
- **Resultado Esperado**: Log exibindo "Banco de dados inicializado com sucesso" e inicialização do sistema sem erros de conexão.

---

## 🔀 4. Git Flow & Checklist de Pull Request (PR)

### Comandos Git para abrir a Branch:
```bash
git checkout main
git pull origin main
git checkout -b feature/docker-integration
```

### Mensagem de Commit Padronizada:
`feat(docker): add Dockerfile, docker-compose.yml and entrypoint script for one-click deployment`

### Critérios para Aprovação do PR:
- [ ] `docker compose up --build` constrói a imagem e sobe os serviços `db` e `app` sem erros.
- [ ] As tabelas e dados iniciais são criados no container PostgreSQL automaticamente.
