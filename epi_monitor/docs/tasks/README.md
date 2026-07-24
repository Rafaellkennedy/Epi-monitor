# 🗺️ EPI Monitor — Guia de Refatoração & Git Flow

Este diretório contém a documentação técnica completa e individualizada de cada problema identificado no projeto, a solução passo a passo, a suíte de testes exigida e o fluxo de branches Git (Git Flow).

---

## 📋 Lista de Tasks & Branches

| Task ID | Documento | Descrição do Problema | Branch Git |
| :--- | :--- | :--- | :--- |
| **TASK-01** | [Task 01: Otimização de RAM](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/docs/tasks/task-01-pre-buffer-ram-optimization.md) | Estouro de RAM pelo pre-buffer de vídeo | `feature/fix-pre-buffer-ram-leak` |
| **TASK-02** | [Task 02: Batch Inference IA](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/docs/tasks/task-02-yolo-batch-inference.md) | Trava do GIL e subaproveitamento da GPU | `feature/yolo-batch-inference` |
| **TASK-03** | [Task 03: Renderização UI](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/docs/tasks/task-03-ui-video-rendering-optimization.md) | Congelamento da interface Qt por escala CPU | `feature/ui-video-rendering-fps` |
| **TASK-04** | [Task 04: ByteTrack & Debounce](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/docs/tasks/task-04-bytetrack-and-temporal-debounce.md) | Falsos alarmes por oclusão momentânea | `feature/bytetrack-temporal-debounce` |
| **TASK-05** | [Task 05: Migrações Alembic & SQL](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/docs/tasks/task-05-alembic-migrations-sql-indexes.md) | Schema estático e queries lentas sem índice | `feature/alembic-migrations-indexes` |
| **TASK-06** | [Task 06: Gestão de Usuários](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/docs/tasks/task-06-user-management-ui.md) | Ausência de CRUD de Usuários na UI | `feature/user-management-crud` |
| **TASK-07** | [Task 07: Polígono ROI](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/docs/tasks/task-07-roi-polygon-detection.md) | Processamento de áreas fora da zona de risco | `feature/roi-polygon-detection` |
| **TASK-08** | [Task 08: Telegram & WhatsApp](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/docs/tasks/task-08-telegram-whatsapp-alerts.md) | Métodos de notificação remota pendentes | `feature/telegram-whatsapp-alerts` |

---

## 🔀 Fluxo de Trabalho Recomendado (Git Flow)

Para cada task acima, siga o procedimento:

1. **Criar a branch a partir da `main`**:
   ```bash
   git checkout main
   git pull origin main
   git checkout -b <NOME_DA_BRANCH>
   ```

2. **Desenvolver e Executar a Suíte de Testes**:
   ```bash
   pytest tests/<TESTE_DA_TASK>.py -v
   ```

3. **Fazer o Commit com mensagem padronizada**:
   ```bash
   git add .
   git commit -m "fix/feat(...): descrição clara da alteração"
   ```

4. **Publicar a Branch e Abrir o Pull Request (PR)**:
   ```bash
   git push origin <NOME_DA_BRANCH>
   ```
