#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

if command -v python3.9 >/dev/null 2>&1; then
  PY_BIN="$(command -v python3.9)"
else
  PY3_VER="$(python3 --version 2>/dev/null || true)"
  if echo "$PY3_VER" | grep -q "Python 3.9"; then
    PY_BIN="$(command -v python3)"
  else
    echo "[ERROR] Python 3.9 no esta disponible en esta cuenta IONOS."
    echo "        Version detectada: ${PY3_VER:-no disponible}"
    echo "        Sin sudo no puedes instalar Python del sistema."
    echo "        Opciones: activar Python 3.9 en panel IONOS o usar la version disponible y ajustar requirements."
    exit 1
  fi
fi

echo "[INFO] Usando Python: $PY_BIN"
"$PY_BIN" -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

cat <<'EOF'
[OK] Entorno listo.
Siguientes pasos:
1) Ajusta .htaccess -> PassengerPython con ruta absoluta a .venv/bin/python
2) Reinicia Passenger desde panel IONOS
3) Revisa logs si hay error de arranque
EOF
