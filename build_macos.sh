#!/bin/bash
# Construit une vraie appli macOS "Feather Ghost.app" + un .dmg (glisser-déposer) + un .pkg (assistant d'installation).
# À lancer SUR UN MAC (ou par GitHub Actions, voir PUBLIER-SUR-GITHUB.txt).
set -e
cd "$(dirname "$0")"

python3 -m pip install --upgrade pip pyinstaller pynput

# Icône .icns
ICONSET="build_icon/feather_ghost.iconset"
rm -rf build_icon && mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z $s $s feather_ghost.png --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  sips -z $((s*2)) $((s*2)) feather_ghost.png --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o build_icon/feather_ghost.icns

# Application
python3 -m PyInstaller --noconfirm --clean --windowed \
  --name "Feather Ghost" \
  --icon build_icon/feather_ghost.icns \
  --osx-bundle-identifier com.featherghost.app \
  --add-data "feather_ghost.png:." \
  --collect-submodules pynput \
  feather_ghost.py
APP="dist/Feather Ghost.app"

# .pkg : assistant d'installation -> /Applications
rm -rf pkgroot && mkdir -p pkgroot
cp -R "$APP" pkgroot/
pkgbuild --analyze --root pkgroot components.plist >/dev/null
/usr/libexec/PlistBuddy -c "Set :0:BundleIsRelocatable false" components.plist
pkgbuild --root pkgroot --component-plist components.plist \
  --install-location /Applications --identifier com.featherghost.pkg --version 1.0 FeatherGhost.pkg

# .dmg : fenêtre avec l'appli + raccourci Applications (glisser-déposer)
rm -rf dmgroot && mkdir -p dmgroot
cp -R "$APP" dmgroot/
ln -s /Applications dmgroot/Applications
hdiutil create -volname "Feather Ghost" -srcfolder dmgroot -ov -format UDZO FeatherGhost.dmg

echo "Terminé : FeatherGhost.dmg et FeatherGhost.pkg"
