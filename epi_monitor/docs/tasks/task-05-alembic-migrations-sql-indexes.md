# Task 05: Migrações de Banco de Dados com Alembic e Índices Otimizados SQL

## 📌 Informações da Task & Git Flow

- **ID:** TASK-05
- **Título:** Configuração do Alembic para Migrações Versionadas e Criação de Índices em `eventos`
- **Branch Recomendada:** `feature/alembic-migrations-indexes`
- **Base Branch:** `main` ou `develop`
- **Arquivos Afetados:**
  - [database/models.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/database/models.py)
  - [database/connection.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/database/connection.py)
  - `alembic.ini` (Novo)
  - `alembic/` (Novo diretório)

---

## 🔴 1. O que está errado (Diagnóstico do Problema)

### Sintoma
1. **Incapacidade de Alterar o Schema em Produção**: Se uma nova coluna for adicionada às tabelas (ex.: novo tipo de alerta), o método `Base.metadata.create_all()` ignora tabelas que já existem. O banco do cliente não é atualizado a menos que seja deletado e recriado do zero.
2. **Consultas Lentíssimas no Dashboard**: À medida que a tabela `eventos` cresce (ex.: 50.000 registros), a abertura da tela de Dashboard trava por alguns segundos executando **Full Table Scan** no PostgreSQL.

### Causa Raiz
No arquivo [database/models.py](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/database/models.py#L134-L146), a tabela `eventos` possui índice simples apenas na coluna `data_hora`. As consultas do `EventService.estatisticas_dashboard()` filtram simultaneamente por `data_hora`, `tipo_evento` e `camera_id`:

```python
# CÓDIGO ATUAL COM DEFEITO (event_service.py)
# Sem índice composto, o PostgreSQL lê todas as linhas do disco para filtrar!
select(func.count(Evento.id)).where(
    Evento.tipo_evento == TipoEvento.INFRACAO, Evento.data_hora >= desde
)
```

---

## 🟢 2. Caminho para a Solução (Guia de Refatoração)

### Estratégia de Refatoração:
1. **Inicializar o Alembic**:
   ```bash
   alembic init alembic
   ```
2. **Configurar `alembic/env.py`**: Conectar o Alembic às variáveis do `config.settings.settings.database.url` e ao `database.models.Base.metadata`.
3. **Adicionar Índices Compostos em [`database/models.py`](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/database/models.py)**:
   - Index composto em `eventos`: `Index("idx_evento_data_tipo", "data_hora", "tipo_evento")`
   - Index composto em `eventos`: `Index("idx_evento_camera_tipo_data", "camera_id", "tipo_evento", "data_hora")`
4. **Gerar a Primeira Migração**:
   ```bash
   alembic revision --autogenerate -m "001_initial_schema_and_indexes"
   ```

### Passo a Passo de Código:

#### Alteração 1: Adicionar Índices em `Evento` em [`database/models.py`](file:///Users/marcofilho1/Desktop/things/Epi-monitor/epi_monitor/database/models.py#L127-L135)
```python
from sqlalchemy import Index

class Evento(Base):
    __tablename__ = "eventos"
    __table_args__ = (
        Index("idx_evento_data_tipo", "data_hora", "tipo_evento"),
        Index("idx_evento_camera_tipo_data", "camera_id", "tipo_evento", "data_hora"),
    )
    # ... (restante das colunas)
```

#### Alteração 2: Atualizar `alembic/env.py`
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings
from database.models import Base

config.set_main_option("sqlalchemy.url", settings.database.url)
target_metadata = Base.metadata
```

---

## 🧪 3. Plano de Testes (Antes de Fazer Merge)

### A. Teste de Aplicação de Migrações (Automático/CLI)
Rodar a migração para frente e para trás para garantir idempotência:

```bash
# Aplica a migração até a versão mais recente (upgrade)
alembic upgrade head

# Reverte a migração (downgrade)
alembic downgrade base

# Re-aplica para deixar o banco atualizado
alembic upgrade head
```

### B. Teste de Performance de Query (EXPLAIN ANALYZE)
Executar via `psql` ou DBeaver no PostgreSQL:
```sql
EXPLAIN ANALYZE 
SELECT count(id) 
FROM eventos 
WHERE tipo_evento = 'infracao' AND data_hora >= NOW() - INTERVAL '7 days';
```
- **Resultado Esperado**: Deve mostrar `Index Scan using idx_evento_data_tipo` em vez de `Seq Scan`.

---

## 🔀 4. Git Flow & Checklist de Pull Request (PR)

### Comandos Git para abrir a Branch:
```bash
git checkout main
git pull origin main
git checkout -b feature/alembic-migrations-indexes
```

### Mensagem de Commit Padronizada:
`feat(db): setup Alembic migrations and add composite indexes for Evento table`

### Critérios para Aprovação do PR:
- [ ] O comando `alembic upgrade head` é executado sem erros.
- [ ] O plano de execução SQL confirma o uso dos índices compostos nas consultas do Dashboard.
