#!/usr/bin/env bash
# Build a Linux AppImage from the PyInstaller output.
# Best-effort packaging; Windows is the primary target.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

APPDIR="build/BOBOzip.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"

echo "[appimage] copying binary..."
cp dist/BOBOzip "$APPDIR/usr/bin/BOBOzip"
chmod +x "$APPDIR/usr/bin/BOBOzip"

# Desktop entry
cat > "$APPDIR/BOBOzip.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=BOBOzip
Exec=BOBOzip
Icon=bobozip
Categories=Utility;Archiving;
Terminal=false
EOF

# Icon (256x256 PNG)
python packaging/make_appimage_icon.py "$APPDIR/bobozip.png"

# AppRun launcher
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "${HERE}/usr/bin/BOBOzip" "$@"
EOF
chmod +x "$APPDIR/AppRun"

echo "[appimage] downloading appimagetool..."
TOOL="build/appimagetool"
if [ ! -f "$TOOL" ]; then
  curl -sSL -o "$TOOL" \
    "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
  chmod +x "$TOOL"
fi

echo "[appimage] building..."
ARCH=x86_64 "$TOOL" "$APPDIR" "dist/BOBOzip-x86_64.AppImage"
echo "[appimage] done -> dist/BOBOzip-x86_64.AppImage"
