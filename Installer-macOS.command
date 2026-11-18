#!/bin/bash
# Feather Ghost — installateur macOS (double-clic).
# Installe l'appli dans ~/Applications/Feather Ghost.app

cd "$(dirname "$0")" || exit 1
SRC="$(pwd)"
DATA="$HOME/Library/Application Support/FeatherGhost"
APP="$HOME/Applications/Feather Ghost.app"

echo "=== Installation de Feather Ghost ==="

# Le fichier vient d'un téléchargement : on enlève le blocage de macOS
xattr -dr com.apple.quarantine "$SRC" 2>/dev/null

# 1) Trouver un Python avec Tk >= 8.6 (le Python d'Apple est trop vieux)
find_python() {
  for p in /opt/homebrew/bin/python3 /usr/local/bin/python3 \
           /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
           /usr/bin/python3 python3; do
    if command -v "$p" >/dev/null 2>&1 && \
       "$p" -c "import tkinter,sys; sys.exit(0 if tkinter.TkVersion >= 8.6 else 1)" 2>/dev/null; then
      echo "$p"; return 0
    fi
  done
  return 1
}

PY="$(find_python)"
if [ -z "$PY" ]; then
  if command -v brew >/dev/null 2>&1; then
    echo "Python avec Tk introuvable : installation via Homebrew…"
    brew install python-tk
    PY="$(find_python)"
  fi
fi
if [ -z "$PY" ]; then
  echo ""
  echo "Il manque Python 3 (avec Tk). Je t'ouvre la page de téléchargement :"
  echo "installe-le, puis double-clique de nouveau sur ce fichier."
  open "https://www.python.org/downloads/macos/"
  read -n 1 -s -r -p "Appuie sur une touche pour fermer."
  exit 1
fi
echo "Python utilisé : $PY"

# 2) Copier l'appli + environnement isolé
mkdir -p "$DATA"
cp -f "$SRC/feather_ghost.py" "$SRC/feather_ghost.png" "$DATA/"
if [ ! -d "$DATA/venv" ]; then
  "$PY" -m venv "$DATA/venv" || { echo "Échec de la création de l'environnement."; exit 1; }
fi
"$DATA/venv/bin/python" -m pip install --upgrade pip >/dev/null 2>&1
"$DATA/venv/bin/python" -m pip install pynput || { echo "Échec de l'installation de pynput."; exit 1; }

# 3) Fabriquer l'application « Feather Ghost.app »
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/MacOS/FeatherGhost" <<'EOF'
#!/bin/bash
cd "$HOME/Library/Application Support/FeatherGhost" || exit 1
exec ./venv/bin/python feather_ghost.py
EOF
chmod +x "$APP/Contents/MacOS/FeatherGhost"

cat > "$APP/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Feather Ghost</string>
  <key>CFBundleDisplayName</key><string>Feather Ghost</string>
  <key>CFBundleIdentifier</key><string>com.featherghost.app</string>
  <key>CFBundleExecutable</key><string>FeatherGhost</string>
  <key>CFBundleIconFile</key><string>feather_ghost</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
EOF

# 4) Icône (.icns) à partir du PNG
ICONSET="$(mktemp -d)/feather_ghost.iconset"
mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z $s $s "$SRC/feather_ghost.png" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null 2>&1
  sips -z $((s*2)) $((s*2)) "$SRC/feather_ghost.png" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null 2>&1
done
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/feather_ghost.icns" 2>/dev/null

touch "$APP"
echo ""
echo "✔ Installé : $APP"
echo ""
echo "IMPORTANT (une seule fois) : au premier lancement, macOS demande l'autorisation"
echo "de contrôler le clavier. Va dans Réglages Système > Confidentialité et sécurité,"
echo "et active Feather Ghost / Python dans :"
echo "   - Accessibilité"
echo "   - Surveillance de l'entrée"
echo ""
open -R "$APP"
read -n 1 -s -r -p "Appuie sur une touche pour fermer."
