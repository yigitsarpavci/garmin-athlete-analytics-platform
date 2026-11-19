#!/usr/bin/env bash
# Tailwind yardımcı sınıflarını tek bir statik dosyaya derler: app/static/css/tailwind.css
# Kullanım: ./tools/build_css.sh   (veya: make css)
# Node 18+ gerekir; Tailwind sürümü sabittir (3.4.17) ve npx ile geçici olarak çalıştırılır.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
npx --yes tailwindcss@3.4.17 -c tailwind.config.js -i tools/tailwind-input.css -o app/static/css/tailwind.css --minify
echo "app/static/css/tailwind.css güncellendi ($(wc -c < app/static/css/tailwind.css | tr -d ' ') bayt)"
