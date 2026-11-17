#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
mkdir -p "$ROOT_DIR/reports" "$ROOT_DIR/data/exports"

if [[ "${1:-}" == "--fetch" ]]; then
  echo "==> [1/3] Garmin Connect'ten son 93 günlük veriler çekiliyor..."
  node "$ROOT_DIR/scripts/fetch_garmin_data.mjs"
else
  echo "==> [1/3] Mevcut data/ altındaki ham JSON verileri kullanılıyor (yeniden çekmek için: ./scripts/generate_report.sh --fetch)..."
fi

echo "==> [2/3] İstatistiksel analiz, CSV tabloları ve LaTeX (reports/report.tex) üretiliyor..."
python3 "$ROOT_DIR/scripts/build_latex_report.py"

echo "==> [3/3] Tectonic (XeLaTeX) ile PDF derleniyor..."
TECTONIC_BIN=$(command -v tectonic || echo "/opt/homebrew/bin/tectonic")
"$TECTONIC_BIN" "$ROOT_DIR/reports/report.tex" -o "$ROOT_DIR/reports"
mv "$ROOT_DIR/reports/report.pdf" "$ROOT_DIR/reports/Garmin_3_Aylik_Detayli_Veri_Analizi_Raporu.pdf"

echo "==> Tamamlandı: $ROOT_DIR/reports/Garmin_3_Aylik_Detayli_Veri_Analizi_Raporu.pdf"
