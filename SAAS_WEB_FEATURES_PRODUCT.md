# Visão de Produto: Funcionalidades do Portal Web (SaaS)

Este documento descreve as funcionalidades essenciais e os diferenciais competitivos que devem compor a **Interface Web do Gerente (Frontend)** na versão SaaS do EPI Monitor.

O objetivo do portal Web não é substituir o sistema de alertas em tempo real (que já ocorre via WhatsApp/Telegram para os fiscais na fábrica), mas sim fornecer ferramentas de **Inteligência de Negócios (BI)**, **Auditoria** e **Gestão de Risco** para engenheiros de segurança do trabalho, gerentes de obra e diretores.

---

## 1. Dashboard Principal (Analytics & BI)

Ao fazer login, o gestor deve ter uma visão "helicóptero" da segurança da sua empresa:

* **Índice de Conformidade Geral (Score):** Uma nota de 0 a 100% indicando o nível de segurança da obra nas últimas 24h.
* **Gráfico de Infrações ao Longo do Tempo:** Gráfico de linhas (Diário/Semanal/Mensal) para identificar se as normas estão sendo mais respeitadas ou negligenciadas com o passar do tempo.
* **Top Infrações por Tipo de EPI:** Gráfico de pizza ou barras identificando os maiores ofensores. Exemplo: *65% Ausência de Óculos, 20% Ausência de Luvas, 15% Ausência de Capacete.*
* **Ranking de Câmeras/Setores Perigosos:** Uma lista mostrando quais câmeras mais registram ocorrências, permitindo ao gestor focar o treinamento de segurança nos setores corretos (ex: *Setor de Solda lidera as infrações*).

## 2. Central de Evidências (Auditoria de Ocorrências)

Esta será a tela mais acessada em casos de acidentes, processos trabalhistas ou auditorias do Ministério do Trabalho.

* **Feed Histórico:** Uma tabela paginada com filtro avançado (por data, por câmera, por gravidade e por tipo de EPI ausente).
* **Player de Vídeo Integrado:** Ao clicar em um evento, abre-se um modal (janela) tocando automaticamente o vídeo `.mp4` (de 10 segundos) resgatado do Cloud Storage (ex: Amazon S3). O vídeo deve mostrar claramente os segundos *antes* e *depois* da infração.
* **Visualização do Snapshot Analisado:** Exibição da imagem em alta resolução com as caixas vermelhas (Bounding Boxes) desenhadas pela Inteligência Artificial, comprovando matematicamente a infração.
* **Exportação Judicial (Download):** Botão para baixar um relatório PDF da infração junto com o arquivo de vídeo original para uso como prova legal.

## 3. Gestão de Câmeras e Zonas de Risco (Operacional)

Os gestores e o suporte técnico precisam de autonomia para gerenciar o parque de câmeras.

* **Live View (Mosaico de Câmeras):** Uma tela com as transmissões em tempo real (via WebRTC para baixar latência) permitindo ao gerente visualizar o chão de fábrica remotamente.
* **Configuração de Polígonos ROI Interativos:** O gerente não deve precisar enviar coordenadas JSON. A interface Web deve carregar um frame ao vivo da câmera e permitir que o usuário "desenhe com o mouse" o polígono de risco na tela. O Frontend converte esse desenho para JSON e salva no Banco de Dados.
* **Configuração de EPIs Obrigatórios:** Opção fácil (Checkboxes) para ligar e desligar quais EPIs são cobrados em qual câmera. (ex: Câmera do Escritório = Não cobra nada; Câmera do Andaime = Cobra Capacete e Cinto).

## 4. Diferenciais Premium (Upsell / Planos Mais Caros)

Para aumentar a receita do SaaS (Ticket Médio), a plataforma Web pode oferecer os seguintes módulos como "Add-ons" pagos:

* **Módulo de Reconhecimento Facial integrado ao RH:** Se o YOLO detectar alguém sem EPI, roda um segundo modelo que identifica o rosto cruzando com os crachás do RH. O relatório deixa de mostrar "Uma pessoa estava sem capacete" e passa a mostrar "João da Silva estava sem capacete".
* **Heatmaps (Mapas de Calor):** Visualização de um mapa de calor na planta da fábrica apontando as áreas de maior risco acumulado.
* **Módulo de Gamificação Corporativa:** Ranking automático de "Setor mais Seguro do Mês". Se um setor passar 30 dias sem nenhuma infração registrada na IA, a plataforma dispara um e-mail de premiação e emite um certificado digital de segurança, incentivando a cultura de prevenção.

---

## Resumo do Valor do Produto (Pitch Comercial)

O portal web vende **Previsibilidade e Mitigação de Passivo Trabalhista**. Enquanto o alerta no celular resolve o risco *imediato*, o Dashboard Web resolve o risco *jurídico e financeiro*, justificando a contratação da plataforma por Diretorias e Setores de Compliance.
