#!/usr/bin/env bash
# MintDo — installer for Linux Mint (no root needed).
# Usage:  ./install.sh            install menu launcher + icon
#         ./install.sh --uninstall remove them again
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPS_DIR="$HOME/.local/share/applications"
ICONS_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
BIN_DIR="$HOME/.local/bin"
DESKTOP="$APPS_DIR/mintdo.desktop"
WRAPPER="$BIN_DIR/mintdo"

if [[ "${1:-}" == "--uninstall" ]]; then
    rm -f "$DESKTOP" "$WRAPPER" "$ICONS_DIR/mintdo.svg"
    command -v update-desktop-database >/dev/null && update-desktop-database "$APPS_DIR" || true
    echo "MintDo removed from the menu. Your data stays in ~/.local/share/mintdo/"
    exit 0
fi

mkdir -p "$APPS_DIR" "$ICONS_DIR" "$BIN_DIR"

# 1. Command wrapper so the .desktop file can launch from any directory.
cat > "$WRAPPER" <<EOF
#!/usr/bin/env bash
cd "$SRC"
exec python3 -m mintdo "\$@"
EOF
chmod +x "$WRAPPER"

# 2. Application icon.
cp "$SRC/assets/icon.svg" "$ICONS_DIR/mintdo.svg"

# 3. Menu entry.
cat > "$DESKTOP" <<EOF
[Desktop Entry]
Name=MintDo
GenericName=To-Do List
Comment=A friendly, offline to-do list with lists, tags and streaks
Exec=$WRAPPER
Icon=mintdo
Terminal=false
Type=Application
Categories=Utility;GTK;
Keywords=todo;task;list;reminder;planner;
StartupNotify=true
EOF
chmod 644 "$DESKTOP"

command -v update-desktop-database >/dev/null && update-desktop-database "$APPS_DIR" || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo "✔ MintDo installed."
echo "  • Menu entry : Menu → Accessories → MintDo"
echo "  • Terminal   : mintdo"
echo "  • Data       : ~/.local/share/mintdo/mintdo.db"
echo "Run './install.sh --uninstall' to remove the launcher."
