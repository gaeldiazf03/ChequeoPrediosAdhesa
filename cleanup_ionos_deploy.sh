#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

echo "[INFO] Carpeta actual: $APP_DIR"

echo "[INFO] Eliminando artefactos incompatibles/subidos por error..."
rm -rf .git __pycache__ */__pycache__ .pytest_cache .mypy_cache .ruff_cache
find . -type f -name "*.pyc" -delete
find . -type f -name "*.pyo" -delete
find . -type f -name "*.pyd" -delete

# Si subiste un venv local de Windows, se elimina y se recrea con Python del servidor.
if [ -d ".venv" ]; then
  echo "[INFO] Eliminando .venv para recrearlo en Linux servidor..."
  rm -rf .venv
fi

# Archivos de soporte que no son necesarios en runtime (opcional).
rm -f .python-version
rm -f .htaccess.example .env.production.example
rm -f DEPLOY_IONOS_SFTP.md
rm -f setup_python39_ionos.sh

# No borramos adhesa.db por seguridad de datos.
# Borra database.db solo si confirmas que no se usa.
if [ -f "database.db" ]; then
  echo "[WARN] Existe database.db (posible archivo antiguo)."
  echo "       Si no lo usas, puedes borrarlo con: rm -f database.db"
fi

echo "[INFO] Limpieza base completada."
echo "[INFO] Siguiente paso: recrear entorno Python e instalar deps."
echo "       python3.9 -m venv .venv"
echo "       source .venv/bin/activate"
echo "       pip install -U pip setuptools wheel"
echo "       pip install -r requirements.txt"
