#!/usr/bin/env zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [[ "${1:-}" == "--fetch" ]]; then
  echo "==> [1/3] Garmin Connect'ten son 93 günlük veriler çekiliyor..."
  node "$SCRIPT_DIR/src/fetch_garmin_data.mjs"
else
  echo "==> [1/3] Mevcut data/ altındaki ham JSON verileri kullanılıyor (yeniden çekmek için: ./generate_report.sh --fetch)..."
fi

echo "==> [2/3] İstatistiksel analiz, CSV tabloları ve LaTeX (src/report.tex) üretiliyor..."
python3 "$SCRIPT_DIR/src/build_latex_report.py"

echo "==> [3/3] Tectonic (XeLaTeX) ile PDF derleniyor..."
TECTONIC_BIN=$(command -v tectonic || echo "/opt/homebrew/bin/tectonic")
"$TECTONIC_BIN" "$SCRIPT_DIR/src/report.tex" -o "$SCRIPT_DIR"
mv "$SCRIPT_DIR/report.pdf" "$SCRIPT_DIR/Garmin_3_Aylik_Detayli_Veri_Analizi_Raporu.pdf"

echo "==> Tamamlandı: $SCRIPT_DIR/Garmin_3_Aylik_Detayli_Veri_Analizi_Raporu.pdf"
