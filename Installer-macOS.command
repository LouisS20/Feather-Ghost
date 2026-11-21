#!/bin/bash
# Feather Ghost — installateur macOS (double-clic).
# Compile l'appli (Rust) et l'installe dans ~/Applications/Feather Ghost.app

cd "$(dirname "$0")" || exit 1
SRC="$(pwd)"
APP="$HOME/Applications/Feather Ghost.app"

pause() { read -n 1 -s -r -p "Appuie sur une touche pour fermer."; }
fail()  { echo ""; echo "✘ $1"; pause; exit 1; }

echo "=== Installation de Feather Ghost ==="

# Le fichier vient d'un téléchargement : on enlève le blocage de macOS
xattr -dr com.apple.quarantine "$SRC" 2>/dev/null

# 1) Outils de développement d'Apple (nécessaires pour compiler)
if ! xcode-select -p >/dev/null 2>&1; then
  echo "Les outils de ligne de commande d'Apple sont requis. Une fenêtre d'installation va s'ouvrir."
  xcode-select --install
  fail "Termine cette installation, puis double-clique de nouveau sur ce fichier."
fi

# 2) Rust (installé automatiquement s'il manque)
[ -f "$HOME/.cargo/env" ] && . "$HOME/.cargo/env"
if ! command -v cargo >/dev/null 2>&1; then
  echo "Rust introuvable : installation (environ une minute)…"
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal \
    || fail "Échec de l'installation de Rust (https://rustup.rs)."
  . "$HOME/.cargo/env"
fi

# 3) Compilation (la première fois, quelques minutes)
echo "Compilation en cours…"
bash "$SRC/build_macos.sh" --app-only || fail "La compilation a échoué : copie les messages ci-dessus pour les envoyer."

# 4) Installation
mkdir -p "$HOME/Applications"
rm -rf "$APP"
cp -R "$SRC/dist/Feather Ghost.app" "$APP"
touch "$APP"

echo ""
echo "✔ Installé : $APP"
echo ""
echo "IMPORTANT (une seule fois) : au premier lancement, macOS demande l'autorisation"
echo "de contrôler le clavier. Va dans Réglages Système > Confidentialité et sécurité,"
echo "et active Feather Ghost dans :"
echo "   - Accessibilité"
echo "   - Surveillance de l'entrée"
echo "(Si macOS refuse d'ouvrir l'appli : clic droit > Ouvrir > Ouvrir.)"
echo ""
open -R "$APP"
pause
