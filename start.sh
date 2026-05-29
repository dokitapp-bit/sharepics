#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "=== Shared Pics MVP ==="

# Cria .env se não existir
if [ ! -f .env ]; then
  cp .env.example .env
  echo "→ .env criado a partir do .env.example"
fi

# Cria venv se não existir
if [ ! -d venv ]; then
  echo "→ Criando ambiente virtual…"
  python3 -m venv venv
fi

source venv/bin/activate

echo "→ Instalando dependências…"
pip install -q -r backend/requirements.txt

echo "→ Gerando ícones PWA…"
python generate_icons.py

mkdir -p uploads/{originals,previews,thumbnails,qrcodes/{events,leads}} data

echo ""
echo "✅ Shared Pics rodando em http://localhost:8000"
echo "   Docs da API: http://localhost:8000/docs"
echo ""

uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
