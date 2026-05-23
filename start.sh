#!/usr/bin/env bash
set -e

export FLASK_APP=run.py

# Cria a pasta de uploads. No Railway, RAILWAY_VOLUME_MOUNT_PATH deve apontar para o volume persistente.
mkdir -p "${RAILWAY_VOLUME_MOUNT_PATH:-${UPLOAD_FOLDER:-uploads}}"

# Primeira subida em produção pequena/média: cria tabelas e seed idempotente.
# O seed usa db.create_all(), então o serviço não fica preso esperando SSH para criar o banco.
python -m app.seed

exec gunicorn run:app --bind 0.0.0.0:${PORT:-8080}
