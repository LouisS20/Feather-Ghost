@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Feather Ghost - compilation

where cargo >nul 2>nul
if errorlevel 1 (
    echo Rust n'est pas installe.
    echo Installation automatique via winget...
    winget install -e --id Rustlang.Rustup --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo.
        echo Installation impossible. Installe Rust a la main : https://rustup.rs
        echo Puis relance ce fichier.
        pause
        exit /b 1
    )
    echo.
    echo Rust est installe. FERME cette fenetre et relance compiler.bat
    echo ^(il faut rouvrir une fenetre pour que Windows trouve cargo^).
    pause
    exit /b 0
)

echo Tests...
cargo test --release
if errorlevel 1 (
    echo.
    echo Les tests ont echoue. Copie le message ci-dessus et envoie-le moi.
    pause
    exit /b 1
)

echo.
echo Compilation en cours ^(la premiere fois, compter quelques minutes^)...
cargo build --release
if errorlevel 1 (
    echo.
    echo La compilation a echoue. Copie les erreurs ci-dessus et envoie-les moi.
    pause
    exit /b 1
)

copy /y "target\release\FeatherGhost.exe" "FeatherGhost.exe" >nul
echo.
echo Termine ! FeatherGhost.exe est dans ce dossier.
choice /m "Le lancer maintenant"
if not errorlevel 2 start "" "FeatherGhost.exe"
