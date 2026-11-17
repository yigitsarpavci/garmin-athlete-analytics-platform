#!/usr/bin/env bash
# ==============================================================================
# Garmin Sporcu Asistanı & Canlı Gösterge Paneli Başlatıcı
# Kullanım: ./run_app.sh [port] (varsayılan port: 8085)
# ==============================================================================

PORT=${1:-8085}
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Garmin Sporcu Asistanı Başlatılıyor..."
echo "==> Port: $PORT"
echo "==> Tarayıcıda açmak için: http://localhost:$PORT"
echo "==> Durdurmak için: Ctrl+C"

python3 "$APP_DIR/app/server.py" "$PORT"
