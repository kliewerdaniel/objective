#!/usr/bin/env bash
#
# build-macos.sh — Build objective03 macOS DMG
#
# Usage:
#   ./scripts/build-macos.sh              # Build only
#   ./scripts/build-macos.sh --sign       # Build + sign
#   ./scripts/build-macos.sh --notarize   # Build + sign + notarize
#
# Prerequisites:
#   - Node.js 20+
#   - Python 3.12+ (for backend)
#   - Xcode Command Line Tools
#   - Apple Developer ID certificate (for signing)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ELECTRON_DIR="$ROOT_DIR/electron"

# Parse args
SIGN=false
NOTARIZE=false
for arg in "$@"; do
  case $arg in
    --sign) SIGN=true ;;
    --notarize) NOTARIZE=true; SIGN=true ;;
  esac
done

echo "========================================"
echo "  objective03 macOS Build"
echo "========================================"
echo ""

# 1. Build React frontend
echo "[1/5] Building React frontend..."
cd "$ELECTRON_DIR"
npm ci
npm run build
echo "  Done."
echo ""

# 2. Build Electron app
echo "[2/5] Building Electron app..."
if [ "$SIGN" = true ]; then
  echo "  (signing enabled)"
  npx electron-builder --mac --config electron-builder.yml
else
  npx electron-builder --mac --config electron-builder.yml --config.mac.identity=null
fi
echo "  Done."
echo ""

# 3. Find the DMG
DMG_PATH=$(ls -t "$ELECTRON_DIR/dist/"*.dmg 2>/dev/null | head -1)
if [ -z "$DMG_PATH" ]; then
  echo "ERROR: No DMG found in $ELECTRON_DIR/dist/"
  exit 1
fi
echo "DMG: $DMG_PATH"
echo ""

# 4. Sign DMG (if signing)
if [ "$SIGN" = true ]; then
  echo "[3/5] Signing DMG..."
  IDENTITY="${APPLE_IDENTITY:-Developer ID Application}"
  codesign --force --sign "$IDENTITY" "$DMG_PATH"
  echo "  Done."
  echo ""
else
  echo "[3/5] Skipping DMG signing (use --sign to enable)"
  echo ""
fi

# 5. Notarize (if requested)
if [ "$NOTARIZE" = true ]; then
  echo "[4/5] Notarizing..."
  if [ -z "${APPLE_ID:-}" ] || [ -z "${APPLE_APP_SPECIFIC_PASSWORD:-}" ] || [ -z "${APPLE_TEAM_ID:-}" ]; then
    echo "  WARNING: Missing notarization env vars (APPLE_ID, APPLE_APP_SPECIFIC_PASSWORD, APPLE_TEAM_ID)"
    echo "  Skipping notarization."
  else
    xcrun notarytool submit "$DMG_PATH" \
      --apple-id "$APPLE_ID" \
      --password "$APPLE_APP_SPECIFIC_PASSWORD" \
      --team-id "$APPLE_TEAM_ID" \
      --wait
    echo "  Stapling ticket..."
    xcrun stapler staple "$DMG_PATH"
    echo "  Done."
  fi
  echo ""
else
  echo "[4/5] Skipping notarization (use --notarize to enable)"
  echo ""
fi

# 6. Summary
echo "[5/5] Build complete!"
echo ""
echo "  DMG: $DMG_PATH"
echo "  Size: $(du -h "$DMG_PATH" | cut -f1)"
echo ""
echo "To test: open \"$DMG_PATH\""
