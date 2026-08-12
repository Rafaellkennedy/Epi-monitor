# Blueprint de Arquitetura: Migração de POC Desktop para SaaS

Este documento serve como guia arquitetural para a futura evolução do **EPI Monitor**.
Atualmente, o projeto atua como uma **Prova de Conceito (POC) Desktop** (usando PySide6, OpenCV local e banco de dados isolado). Para transformar o sistema em um produto escalável (Software as a Service - SaaS) capaz de atender múltiplos clientes simultaneamente, a arquitetura deverá ser refatorada seguindo o modelo distribuído abaixo.

---

## 1. Visão Geral da Arquitetura Distribuída

O monolito atual será dividido em três camadas principais:
1. **Edge Node (Cliente):** Responsável apenas por capturar os frames das câmeras locais e enviá-los de forma leve para a nuvem.
2. **Backend Engine (Nuvem):** Clusters de GPU, filas de mensageria e APIs para processamento e armazenamento centralizado.
3. **Frontend (Gerente):** Aplicação Web acessível via browser para relatórios e acompanhamento.

---

## 2. Componentes e Tecnologias Sugeridas

### 2.1. Edge Node (Agente Local)
* **Objetivo:** O cliente não precisa comprar um servidor caro. Um mini-PC (ex: Raspberry Pi 4 ou NUC básico) na mesma rede das câmeras captura o fluxo RTSP.
* **Mecanismo:** Ao invés de mandar o streaming 30 FPS inteiro pela internet, o Edge Node aplica *Frame Skipping* (ex: extrai 2 frames por segundo) e faz um POST HTTP ou gRPC para o servidor na nuvem.
* **Vantagem:** Baixo consumo de banda de upload para o cliente.

### 2.2. Ingestão e Fila de Mensagens (Broker)
* **Tecnologia:** Apache Kafka ou RabbitMQ.
* **Objetivo:** Receber milhares de frames por segundo de vários clientes diferentes sem derrubar o sistema. O Kafka atua como um "amortecedor" (buffer).

### 2.3. Inference Workers (Processamento IA)
* **Tecnologia:** Kubernetes + GPU Nodes (AWS EC2 g4dn, Google Cloud, etc).
* **Mecanismo:** *Workers* assíncronos (escritos em Python) puxam as imagens do Kafka e processam o modelo YOLOv8. Se a fila crescer muito, o Kubernetes sobe mais máquinas automaticamente (Auto-scaling horizontal).
* **Decisão Arquitetural:** O YOLO não fica mais amarrado ao loop da câmera, ele age como um serviço "stateless".

### 2.4. Armazenamento de Evidências (Storage)
* **Tecnologia:** Amazon S3 ou Google Cloud Storage.
* **Mecanismo:** Quando uma infração é detectada, o *Worker* monta o vídeo `.mp4` do evento e faz upload direto para o S3.
* **Vantagem:** Armazenamento praticamente infinito, muito mais barato e seguro do que guardar vídeos no banco de dados ou em HDs locais.

### 2.5. Banco de Dados e Multi-tenancy
* **Tecnologia:** PostgreSQL.
* **Refatoração:** Inclusão do conceito de **Multi-tenant**. Todas as tabelas (`cameras`, `eventos`, `alertas`) receberão a coluna `tenant_id` (ID da Empresa Cliente). A camada de dados usa `Row Level Security (RLS)` ou filtros rigorosos no ORM (SQLAlchemy) para impedir vazamento de dados entre empresas.

### 2.6. API REST & Frontend Web
* **API:** Backend em FastAPI (Python) ou Django para servir os dados aos usuários.
* **Frontend:** Aplicação em React.js ou Next.js. O PySide6 será descontinuado para os clientes finais.
* **Autenticação:** Baseada em tokens JWT. O token carrega a qual `tenant_id` o usuário pertence.
* **Streaming ao Vivo:** Para visualização em tempo real das câmeras pelo navegador, recomenda-se a tecnologia **WebRTC** (menor latência) suportada nativamente pelos browsers modernos.

---

## 3. Fluxograma do Novo Pipeline de Detecção

1. `Edge Node` extrai frame (imagem.jpg) do stream RTSP local.
2. `Edge Node` anexa metadados: `{ tenant_id: 123, camera_id: 456, timestamp: ... }`.
3. `Edge Node` publica payload no tópico `camera.frames` do `Kafka`.
4. `YOLO Worker` (GPU) consome payload, roda inferência e detecta "Sem Capacete".
5. `YOLO Worker` grava o clipe de 10 segundos gerado do buffer e faz upload para `Amazon S3`.
6. `YOLO Worker` insere registro na tabela `eventos` no `PostgreSQL`, salvando a URL do S3.
7. `YOLO Worker` aciona o serviço de Alertas, que manda mensagem para a fila do `WhatsApp/Telegram`.
8. O Gerente acessa o painel Web (`React`), a requisição bate na `API FastAPI` que consulta o `PostgreSQL` e mostra o vídeo baixado do `S3`.

---

## 4. Próximos Passos (Transição)

Para iniciar essa transição de forma segura, mantendo a POC atual operante:
1. **Fase 1 (Separação UI/Core):** Criar uma API REST no projeto atual que forneça os dados (JSON) do banco, mantendo o motor YOLO rodando na mesma máquina.
2. **Fase 2 (Nuvem Inicial):** Hospedar o banco de dados e a API na nuvem. Manter apenas o `CameraStream` e o YOLO na máquina local, enviando *apenas os resultados* via API.
3. **Fase 3 (SaaS Completo):** Mover o YOLO para a nuvem atrás de filas. O computador local torna-se um mero repassador de frames (*Edge Node* simples).
