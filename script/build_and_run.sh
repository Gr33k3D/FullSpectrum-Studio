#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-run}"
APP_NAME="FullSpectrum Studio"
EXECUTABLE_NAME="FullSpectrumStudio"
BUNDLE_ID="studio.fullspectrum.macos"
MIN_SYSTEM_VERSION="14.0"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_VERSION="$(tr -d '[:space:]' < "$ROOT_DIR/VERSION")"
APP_VERSION="${FULLSPECTRUM_VERSION:-$PROJECT_VERSION}"
APP_BUILD="${FULLSPECTRUM_BUILD:-17}"
DIST_DIR="$ROOT_DIR/dist"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"
APP_CONTENTS="$APP_BUNDLE/Contents"
APP_MACOS="$APP_CONTENTS/MacOS"
APP_RESOURCES="$APP_CONTENTS/Resources"
APP_BINARY="$APP_MACOS/$EXECUTABLE_NAME"
INFO_PLIST="$APP_CONTENTS/Info.plist"

pkill -x "$EXECUTABLE_NAME" >/dev/null 2>&1 || true

scrub_bundle_metadata() {
  [[ -d "$APP_BUNDLE" ]] || return 0
  while IFS= read -r -d '' entry; do
    /usr/bin/xattr -c "$entry" >/dev/null 2>&1 || true
    /usr/bin/xattr -d 'com.apple.fileprovider.fpfs#P' "$entry" >/dev/null 2>&1 || true
    /usr/bin/xattr -d com.apple.FinderInfo "$entry" >/dev/null 2>&1 || true
    /usr/bin/xattr -d com.apple.macl "$entry" >/dev/null 2>&1 || true
  done < <(/usr/bin/find "$APP_BUNDLE" -mindepth 1 -print0)
  /usr/bin/xattr -cr "$APP_BUNDLE" >/dev/null 2>&1 || true
  /usr/bin/xattr -c "$APP_BUNDLE" >/dev/null 2>&1 || true
  /usr/bin/xattr -d 'com.apple.fileprovider.fpfs#P' "$APP_BUNDLE" >/dev/null 2>&1 || true
  /usr/bin/xattr -d com.apple.FinderInfo "$APP_BUNDLE" >/dev/null 2>&1 || true
  /usr/bin/xattr -d com.apple.macl "$APP_BUNDLE" >/dev/null 2>&1 || true
}

sign_bundle() {
  local signed=0
  for _ in 1 2 3; do
    scrub_bundle_metadata
    if /usr/bin/codesign --force --deep --sign - --timestamp=none "$APP_BUNDLE"; then
      signed=1
      break
    fi
    sleep 1
  done
  if [[ "$signed" != "1" ]]; then
    exit 1
  fi
}

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
cp "$ROOT_DIR/VERSION" "$APP_RESOURCES/VERSION"
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
  <string>$APP_VERSION</string>
  <key>CFBundleVersion</key>
  <string>$APP_BUILD</string>
  <key>CFBundleGetInfoString</key>
  <string>Local palette planner and Bambu 3MF converter</string>
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
sign_bundle
# Some local folders attach Finder/FileProvider metadata immediately after a
# bundle is written or signed. Remove it again before strict verification.
scrub_bundle_metadata

open_app() {
  /usr/bin/open -n "$APP_BUNDLE"
}

strict_verify_bundle() {
  local verified=0
  for _ in 1 2 3; do
    scrub_bundle_metadata
    if /usr/bin/codesign --verify --deep --strict --verbose=2 "$APP_BUNDLE"; then
      verified=1
      break
    fi
    sleep 1
  done
  if [[ "$verified" != "1" ]]; then
    exit 1
  fi
}

verify_distributable_archive() {
  local temp_dir archive_path extracted_app
  temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/fullspectrum-release.XXXXXX")"
  archive_path="$temp_dir/FullSpectrum-Studio-macOS.zip"
  extracted_app="$temp_dir/extracted/$APP_NAME.app"
  mkdir -p "$temp_dir/extracted"
  /usr/bin/ditto -c -k --norsrc --keepParent "$APP_BUNDLE" "$archive_path"
  /usr/bin/ditto -x -k "$archive_path" "$temp_dir/extracted"
  if ! /usr/bin/codesign --verify --deep --strict --verbose=2 "$extracted_app"; then
    rm -rf "$temp_dir"
    return 1
  fi
  rm -rf "$temp_dir"
}

case "$MODE" in
  build|--build)
    strict_verify_bundle
    verify_distributable_archive
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
    # Launch Services can attach Finder metadata to the local bundle during a
    # verification launch. Remove it so a post-run strict codesign check still
    # reflects the distributable bundle state.
    strict_verify_bundle
    echo "$APP_NAME launched successfully."
    ;;
  *)
    echo "usage: $0 [build|run|--debug|--logs|--telemetry|--verify]" >&2
    exit 2
    ;;
esac
