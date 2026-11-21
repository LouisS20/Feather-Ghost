# Feather Ghost (version Rust)

Le copier-coller qui tape lettre par lettre : colle ton texte, clique sur **Lancer**, puis clique
là où tu veux que ça s'écrive. **Échap** = arrêt d'urgence (même fenêtre inactive).

## Compiler

```
cargo run --release          # lancer
cargo build --release        # → target/release/FeatherGhost(.exe)
cargo test                   # tests du rythme de frappe, de la config, de la couche Windows
```

Sans Rust installé : mets le dossier sur GitHub, onglet **Actions → Build → Run workflow**.
Les exécutables Windows, macOS et Linux sortent dans « Artifacts ».

## Installer sur Mac

- **Sur le Mac** : double-clique sur `Installer-macOS.command` (clic droit > Ouvrir si macOS refuse).
  Il installe Rust si besoin, compile l'appli et la place dans `~/Applications/Feather Ghost.app`.
- **Sans Mac** : sur GitHub, onglet **Actions → Build macOS → Run workflow**, puis télécharge
  `FeatherGhost-macOS` (un `.dmg` à glisser dans Applications et un `.pkg`). L'appli est universelle
  (Apple Silicon + Intel).
- **À la main** : `bash build_macos.sh`.
- Au premier lancement, autorise l'appli dans Réglages Système > Confidentialité et sécurité >
  Accessibilité et « Surveillance de l'entrée ».

## Ce qui est repris de la version Python

- Zone de texte sans limite, compteur de caractères, bouton **Vider**
- Vitesse (1 à 100 car./s), délai après le premier clic (0 à 60 s)
- Rythme « humain », retours à la ligne = Entrée
- Trois façons d'écrire : clavier normal, arrière-plan (Windows), WordCraft (`wordcraft --control 7981`)
- Bouton **Ouvrir WordCraft** (recherche automatique, chemin mémorisé, port réglable)
- Arrêt par Échap ou bouton, barre de progression, messages d'état
- Même fichier de réglages (`%APPDATA%\FeatherGhost\config.json`) : l'ancien `wordcraft_path` est relu

## Ce qui change

- **Thème transparent (Zen)** par défaut, avec flou Acrylic sous Windows (Mica en repli),
  curseur de transparence et interrupteur de flou ; thème « Classique » opaque disponible
  (bouton *Apparence*). Technique du correctif `reflex-rs` : fenêtre transparente, panneaux
  transparents, une seule teinte peinte sur tout le fond.
- Interface arrondie : boutons, pastilles de choix, interrupteurs, cartes, barre de progression.
- Les deux cases « arrière-plan » et « WordCraft » deviennent **un seul choix de mode**
  (plus de priorité cachée entre elles). Le mode par défaut est le clavier normal.
- Tous les réglages sont mémorisés (vitesse, délai, mode, thème…).
- Durée estimée affichée avant de lancer.
- Bouton **Ouvrir un fichier…** pour charger un .txt directement.
- Plus de bibliothèque de hooks : Échap et le premier clic sont lus directement auprès du système.
- Pauses précises sous Windows (minuterie 1 ms) : 100 car./s est vraiment atteint,
  et les pauses ne dérivent plus au fil du texte.
- Les caractères absents du clavier (émojis, etc.) sont envoyés en Unicode.

## Organisation (une étape = un fichier)

| Fichier | Rôle |
|---|---|
| `humanize.rs` | rythme de frappe, durée estimée (testé) |
| `config.rs` | réglages enregistrés (testé) |
| `platform/` | clavier, souris, fenêtres : Windows (user32) ou macOS/Linux (enigo + device_query) |
| `wordcraft.rs` | canal de contrôle de WordCraft |
| `engine.rs` | thread de saisie : premier clic, compte à rebours, frappe, arrêt |
| `theme.rs`, `window.rs` | thèmes classique/zen, flou Acrylic |
| `widgets.rs`, `app.rs` | widgets arrondis et interface |

## Notes

- macOS : autoriser l'appli dans Réglages Système > Confidentialité et sécurité > Accessibilité
  et « Surveillance de l'entrée ». Le mode arrière-plan n'existe pas sur Mac.
- Hors Windows, le thème Zen est une teinte translucide sans flou système.
- Les applis lancées en administrateur ne reçoivent pas la saisie d'une appli normale :
  lance alors Feather Ghost en administrateur aussi.
