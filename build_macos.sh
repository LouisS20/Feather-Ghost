#!/bin/bash
# Construit "Feather Ghost.app", puis un .dmg (glisser-déposer) et un .pkg (assistant d'installation).
# À lancer SUR UN MAC (ou par GitHub Actions : .github/workflows/build-macos.yml).
#
#   bash build_macos.sh              -> appli universelle (Apple Silicon + Intel) + .dmg + .pkg
#   bash build_macos.sh --app-only   -> seulement l'appli pour cette machine (plus rapide)
set -e
cd "$(dirname "$0")"

APP_ONLY=0
[ "$1" = "--app-only" ] && APP_ONLY=1

[ -f "$HOME/.cargo/env" ] && . "$HOME/.cargo/env"
if ! command -v cargo >/dev/null 2>&1; then
  echo "Rust (cargo) est introuvable. Installe-le : https://rustup.rs"
  exit 1
fi

# 1) Exécutable Rust
BIN="target/FeatherGhost-mac"
mkdir -p target
if [ "$APP_ONLY" = "0" ] && command -v rustup >/dev/null 2>&1; then
  rustup target add aarch64-apple-darwin x86_64-apple-darwin
  cargo build --release --target aarch64-apple-darwin
  cargo build --release --target x86_64-apple-darwin
  lipo -create -output "$BIN" \
    target/aarch64-apple-darwin/release/FeatherGhost \
    target/x86_64-apple-darwin/release/FeatherGhost
else
  cargo build --release
  cp target/release/FeatherGhost "$BIN"
fi

# 2) Icône .icns
ICONSET="target/icon/FeatherGhost.iconset"
rm -rf target/icon && mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z $s $s assets/icon_1024.png --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  sips -z $((s*2)) $((s*2)) assets/icon_1024.png --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o target/icon/FeatherGhost.icns

# 3) Application
APP="dist/Feather Ghost.app"
rm -rf dist && mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/FeatherGhost"
chmod +x "$APP/Contents/MacOS/FeatherGhost"
cp target/icon/FeatherGhost.icns "$APP/Contents/Resources/FeatherGhost.icns"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Feather Ghost</string>
  <key>CFBundleDisplayName</key><string>Feather Ghost</string>
  <key>CFBundleIdentifier</key><string>com.featherghost.app</string>
  <key>CFBundleExecutable</key><string>FeatherGhost</string>
  <key>CFBundleIconFile</key><string>FeatherGhost</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>2.0.0</string>
  <key>CFBundleVersion</key><string>2.0.0</string>
  <key>LSMinimumSystemVersion</key><string>10.13</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST
# Signature « ad hoc » : nécessaire pour que les Mac Apple Silicon acceptent de lancer l'appli.
codesign --force --deep --sign - "$APP"

if [ "$APP_ONLY" = "1" ]; then
  echo "Terminé : $APP"
  exit 0
fi

# 4) .pkg : assistant d'installation -> /Applications
rm -rf pkgroot FeatherGhost.pkg components.plist && mkdir -p pkgroot
cp -R "$APP" pkgroot/
pkgbuild --analyze --root pkgroot components.plist >/dev/null
/usr/libexec/PlistBuddy -c "Set :0:BundleIsRelocatable false" components.plist
pkgbuild --root pkgroot --component-plist components.plist \
  --install-location /Applications --identifier com.featherghost.pkg --version 2.0.0 FeatherGhost.pkg

# 5) .dmg : fenêtre avec l'appli + raccourci Applications (glisser-déposer)
rm -rf dmgroot FeatherGhost.dmg && mkdir -p dmgroot
cp -R "$APP" dmgroot/
ln -s /Applications dmgroot/Applications
hdiutil create -volname "Feather Ghost" -srcfolder dmgroot -ov -format UDZO FeatherGhost.dmg

echo "Terminé : FeatherGhost.dmg et FeatherGhost.pkg"
