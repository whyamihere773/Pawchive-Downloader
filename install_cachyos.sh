#!/usr/bin/env bash
# Pawchive Downloader — CachyOS Native Installer
# Automates dependency installation, optimized compilation, and desktop launcher setup.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=================================================================="
echo "  🐧 Pawchive Downloader — CachyOS / Arch Linux Native Installer"
echo "=================================================================="

# Verify running on Arch / CachyOS
if ! command -v pacman &>/dev/null; then
    echo "⚠️  pacman was not detected. This script is intended for CachyOS / Arch Linux."
    echo "   Running generic Linux build instead..."
    exec ./build_linux.sh "$@"
fi

echo "📦 Installing required dependencies via pacman..."
sudo pacman -S --needed --noconfirm \
    python \
    pyside6 \
    qt6-declarative \
    qt6-quickcontrols2 \
    qt6-svg \
    python-pillow \
    python-requests \
    python-urllib3 \
    python-pycryptodome \
    python-mutagen \
    python-qrcode \
    yt-dlp \
    p7zip \
    base-devel

echo ""
echo "Choose installation method:"
echo "  1) Native Arch Package (makepkg -si) — Recommended for CachyOS (clean pacman management)"
echo "  2) Standalone Executable (PyInstaller) — Self-contained binary in dist/"
echo ""
read -r -p "Enter choice [1/2] (default: 1): " choice
choice="${choice:-1}"

if [ "$choice" = "1" ]; then
    echo "\n🔨 Building native package with CachyOS compiler optimizations..."
    makepkg -si --noconfirm
    echo "\n🎉 Installed successfully! You can launch Pawchive Downloader from your app menu or by typing 'pawchive'."
else
    echo "\n🔨 Compiling standalone binary..."
    python3 build_linux.py "$@"
    echo "\n🎉 Build complete! Executable is at dist/Pawchive Downloader/pawchive"
fi
