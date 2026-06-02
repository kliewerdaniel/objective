#!/usr/bin/env bash
#
# generate-assets.sh — Generate placeholder DMG background and app icon
#
# Requires ImageMagick (brew install imagemagick)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$ROOT_DIR/electron/build-resources"

mkdir -p "$BUILD_DIR"

# Check for ImageMagick
if ! command -v convert &>/dev/null; then
  echo "ImageMagick not found. Install with: brew install imagemagick"
  echo ""
  echo "Manual asset requirements:"
  echo "  DMG background: $BUILD_DIR/dmg-background.png (660x400, #0a0a0a background)"
  echo "  App icon:       $BUILD_DIR/icon.icns (1024x1024 source PNG)"
  echo ""
  echo "For the app icon, use: png2icns icon.icns icon_16x16.png icon_32x32.png ..."
  echo "Or use a tool like: https://www.macenhance.com/macgems/icnsutils"
  exit 1
fi

echo "Generating DMG background..."
convert -size 660x400 xc:'#0a0a0a' \
  -fill '#1a1a1a' -draw "roundrectangle 0,0 659,399 8,8" \
  -fill '#00ff88' -pointsize 14 -font Helvetica -gravity center \
  -annotate +0+150 'Drag objective03 to Applications' \
  "$BUILD_DIR/dmg-background.png"

echo "Generating placeholder icon..."
convert -size 1024x1024 xc:'#0a0a0a' \
  -fill '#00ff88' -draw "circle 512,512 512,128" \
  -fill '#0a0a0a' -draw "circle 512,512 512,256" \
  -fill '#00ff88' -draw "circle 512,512 512,320" \
  "$BUILD_DIR/icon.png"

echo ""
echo "Generated:"
echo "  $BUILD_DIR/dmg-background.png"
echo "  $BUILD_DIR/icon.png"
echo ""
echo "To create .icns from icon.png:"
echo "  1. Use https://cloudconvert.com/png-to-icns"
echo "  2. Or: iconutil -c icns --output $BUILD_DIR/icon.icns icon.iconset"
echo ""
echo "For production, create a proper 1024x1024 icon with:"
echo "  - Dark background (#0a0a0a)"
echo "  - Radio tower silhouette"
echo "  - Pulsing dot at top"
