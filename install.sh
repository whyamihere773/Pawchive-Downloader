#!/usr/bin/env sh
# Pawchive Downloader — Portable Linux Desktop Integration Installer
# Installs a working application launcher (.desktop), icon, pawchive:// URL
# handler, and ~/.local/bin/pawchive symlink pointing to this exact folder.
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
APP_BIN="${SCRIPT_DIR}/pawchive"

if [ ! -x "${APP_BIN}" ]; then
    echo "Error: '${APP_BIN}' not found or not executable." >&2
    echo "Run this script from inside the extracted pawchive-downloader folder." >&2
    exit 1
fi

XDG_DATA_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}"
APPS_DIR="${XDG_DATA_HOME}/applications"
ICONS_DIR="${XDG_DATA_HOME}/icons/hicolor/512x512/apps"
BIN_DIR="${HOME}/.local/bin"

mkdir -p "${APPS_DIR}" "${ICONS_DIR}" "${BIN_DIR}"

# Install icon to hicolor theme (also fall back to local PNG if missing)
ICON_SRC=""
for candidate in "${SCRIPT_DIR}/pawchive.png" "${SCRIPT_DIR}/assets/pawchive.png" "${SCRIPT_DIR}/icon.png"; do
    if [ -f "${candidate}" ]; then
        ICON_SRC="${candidate}"
        break
    fi
done

ICON_ENTRY="pawchive"
if [ -n "${ICON_SRC}" ]; then
    cp -f "${ICON_SRC}" "${ICONS_DIR}/pawchive.png"
    ICON_ENTRY="${ICONS_DIR}/pawchive.png"
fi

# Escape double quotes / backslashes for the Desktop Entry Exec key
ESCAPED_BIN="$(printf '%s' "${APP_BIN}" | sed 's/\\/\\\\/g; s/"/\\"/g')"

DESKTOP_FILE="${APPS_DIR}/pawchive.desktop"
cat > "${DESKTOP_FILE}" <<EOF
[Desktop Entry]
Name=Pawchive Downloader
GenericName=Media Downloader & Archival Suite
Comment=Universal Cross-Platform Pawchive, Kemono, Coomer, Bunkr & Fanbox Archival Suite
Exec="${ESCAPED_BIN}" %U
Path=${SCRIPT_DIR}
Icon=${ICON_ENTRY}
Terminal=false
Type=Application
Categories=Network;FileTransfer;Utility;Archiving;
StartupNotify=true
StartupWMClass=PawchiveDownloader
MimeType=x-scheme-handler/pawchive;
Keywords=pawchive;kemono;coomer;bunkr;fanbox;downloader;archival;
EOF
chmod 644 "${DESKTOP_FILE}"

# Create convenient CLI symlink if not colliding with a non-symlink binary
LINK_PATH="${BIN_DIR}/pawchive"
if [ ! -e "${LINK_PATH}" ] || [ -L "${LINK_PATH}" ]; then
    ln -sf "${APP_BIN}" "${LINK_PATH}"
fi

# Refresh desktop database & icon cache so menu entry and pawchive:// links work right away
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${APPS_DIR}" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "${XDG_DATA_HOME}/icons/hicolor" >/dev/null 2>&1 || true
fi
if command -v xdg-mime >/dev/null 2>&1; then
    xdg-mime default pawchive.desktop x-scheme-handler/pawchive >/dev/null 2>&1 || true
fi

echo "Pawchive Downloader desktop integration installed!"
echo "  Launcher : ${DESKTOP_FILE}"
echo "  Icon     : ${ICON_ENTRY}"
echo "  Command  : ${LINK_PATH}"
echo ""
echo "Tip: If your GPU driver has OpenGL issues, launch with: ./pawchive --software-render"
echo "To remove desktop integration later, run: ./uninstall.sh"
