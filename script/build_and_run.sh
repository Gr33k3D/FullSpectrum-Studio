#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-run}"
APP_NAME="FullSpectrum Studio"
EXECUTABLE_NAME="FullSpectrumStudio"
BUNDLE_ID="studio.fullspectrum.macos"
MIN_SYSTEM_VERSION="14.0"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"
APP_CONTENTS="$APP_BUNDLE/Contents"
APP_MACOS="$APP_CONTENTS/MacOS"
APP_RESOURCES="$APP_CONTENTS/Resources"
APP_BINARY="$APP_MACOS/$EXECUTABLE_NAME"
INFO_PLIST="$APP_CONTENTS/Info.plist"

pkill -x "$EXECUTABLE_NAME" >/dev/null 2>&1 || true

cd "$ROOT_DIR"
swift build -c release
BIN_DIR="$(swift build -c release --show-bin-path)"
BUILD_BINARY="$BIN_DIR/$EXECUTABLE_NAME"

rm -rf "$APP_BUNDLE"
mkdir -p "$APP_MACOS" "$APP_RESOURCES"
cp "$BUILD_BINARY" "$APP_BINARY"
cp "$ROOT_DIR/fullspectrum_engine.py" "$APP_RESOURCES/FullSpectrumEngine.py"
cp "$ROOT_DIR/bambu_mixer_model.py" "$APP_RESOURCES/bambu_mixer_model.py"
cp "$ROOT_DIR/LICENSE" "$APP_RESOURCES/LICENSE"
cp "$ROOT_DIR/THIRD_PARTY_NOTICES.md" "$APP_RESOURCES/THIRD_PARTY_NOTICES.md"
chmod +x "$APP_BINARY" "$APP_RESOURCES/FullSpectrumEngine.py"
# Prevent local compiler path/debug symbols from travelling in a shared app ZIP.
/usr/bin/strip -S -x "$APP_BINARY"

cat >"$INFO_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>$EXECUTABLE_NAME</string>
  <key>CFBundleIdentifier</key>
  <string>$BUNDLE_ID</string>
  <key>CFBundleName</key>
  <string>$APP_NAME</string>
  <key>CFBundleDisplayName</key>
  <string>$APP_NAME</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>0.4.3</string>
  <key>CFBundleVersion</key>
  <string>7</string>
  <key>CFBundleGetInfoString</key>
  <string>Community Preview - validated local reduced-filament workflow</string>
  <key>LSMinimumSystemVersion</key>
  <string>$MIN_SYSTEM_VERSION</string>
  <key>NSPrincipalClass</key>
  <string>NSApplication</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>CFBundleDocumentTypes</key>
  <array>
    <dict>
      <key>CFBundleTypeExtensions</key>
      <array>
        <string>3mf</string>
        <string>obj</string>
        <string>glb</string>
      </array>
      <key>CFBundleTypeName</key>
      <string>Painted 3MF or Textured OBJ/GLB Source</string>
      <key>CFBundleTypeRole</key>
      <string>Editor</string>
    </dict>
  </array>
</dict>
</plist>
PLIST

# Seal the completed bundle after all resources have been copied. This is an
# ad-hoc signature for community downloads, not Developer ID notarization.
/usr/bin/xattr -cr "$APP_BUNDLE"
/usr/bin/codesign --force --deep --sign - --timestamp=none "$APP_BUNDLE"
/usr/bin/codesign --verify --deep --strict --verbose=2 "$APP_BUNDLE"

open_app() {
  /usr/bin/open -n "$APP_BUNDLE"
}

case "$MODE" in
  build|--build)
    echo "$APP_NAME built at $APP_BUNDLE."
    ;;
  run)
    open_app
    ;;
  --debug|debug)
    lldb -- "$APP_BINARY"
    ;;
  --logs|logs)
    open_app
    /usr/bin/log stream --info --style compact --predicate "process == \"$EXECUTABLE_NAME\""
    ;;
  --telemetry|telemetry)
    open_app
    /usr/bin/log stream --info --style compact --predicate "subsystem == \"$BUNDLE_ID\""
    ;;
  --verify|verify)
    open_app
    sleep 1
    pgrep -x "$EXECUTABLE_NAME" >/dev/null
    echo "$APP_NAME launched successfully."
    ;;
  *)
    echo "usage: $0 [build|run|--debug|--logs|--telemetry|--verify]" >&2
    exit 2
    ;;
esac
