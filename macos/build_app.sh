#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_NAME="Garmin Sporcu Paneli"
BUNDLE_ID="com.sarp.garmin-sporcu-paneli"

BUILD_DIR="$SCRIPT_DIR/build"
APP_BUNDLE="$BUILD_DIR/${APP_NAME}.app"
CONTENTS="$APP_BUNDLE/Contents"
MACOS_DIR="$CONTENTS/MacOS"
RES_DIR="$CONTENTS/Resources"
ICONSET="$BUILD_DIR/AppIcon.iconset"

rm -rf "$BUILD_DIR"
mkdir -p "$MACOS_DIR" "$RES_DIR" "$ICONSET"

echo "1/4 Compiling native WKWebView app..."
swiftc -O -framework Cocoa -framework WebKit \
  "$SCRIPT_DIR/GarminApp.swift" \
  -o "$MACOS_DIR/$APP_NAME"

echo "2/4 Generating app icon..."
python3 "$SCRIPT_DIR/make_icon.py" "$BUILD_DIR/icon_1024.png"
for sz in 16 32 128 256 512; do
  sips -z "$sz" "$sz" "$BUILD_DIR/icon_1024.png" --out "$ICONSET/icon_${sz}x${sz}.png" >/dev/null
  sz2=$((sz * 2))
  sips -z "$sz2" "$sz2" "$BUILD_DIR/icon_1024.png" --out "$ICONSET/icon_${sz}x${sz}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$RES_DIR/AppIcon.icns"

echo "3/4 Writing Info.plist & signing..."
cat > "$CONTENTS/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>tr</string>
  <key>CFBundleExecutable</key>
  <string>${APP_NAME}</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundleIdentifier</key>
  <string>${BUNDLE_ID}</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>${APP_NAME}</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>2.0.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>13.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>ProjectDir</key>
  <string>${PROJECT_DIR}</string>
</dict>
</plist>
PLIST

codesign --force --deep --sign - "$APP_BUNDLE" >/dev/null 2>&1 || true

echo "4/4 Installing to Desktop and ~/Applications..."
mkdir -p "$HOME/Desktop" "$HOME/Applications"
rm -rf "$HOME/Desktop/${APP_NAME}.app" "$HOME/Applications/${APP_NAME}.app"
cp -R "$APP_BUNDLE" "$HOME/Desktop/${APP_NAME}.app"
cp -R "$APP_BUNDLE" "$HOME/Applications/${APP_NAME}.app"
rm -rf "$BUILD_DIR"

echo "Done! Installed:"
echo "  - $HOME/Desktop/${APP_NAME}.app"
echo "  - $HOME/Applications/${APP_NAME}.app"
