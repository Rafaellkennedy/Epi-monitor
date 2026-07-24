#!/usr/bin/env bash
set -e

echo "🐳 [Docker Entrypoint] Aguardando banco de dados PostgreSQL em ${DB_HOST:-db}:${DB_PORT:-5432}..."

until nc -z -v -w30 "${DB_HOST:-db}" "${DB_PORT:-5432}"; do
  echo "⏳ PostgreSQL ainda indisponível - aguardando..."
  sleep 2
done

echo "✅ [Docker Entrypoint] Conexão com PostgreSQL estabelecida com sucesso!"

echo "🔄 [Docker Entrypoint] Executando inicialização de tabelas e seed do banco..."
python scripts/setup_database.py

echo "🚀 [Docker Entrypoint] Iniciando aplicação EPI Monitor..."
exec "$@"
