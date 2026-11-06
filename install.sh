#!/usr/bin/env bash
# Install vibe-sessions: put it on PATH and wire up Alt+V / `vibe -s`.
#
#   ./install.sh              install to ~/.local/bin and add the bashrc block
#   ./install.sh --no-bashrc  install the command only
#   ./install.sh --uninstall  remove the command and the bashrc block
set -euo pipefail

PREFIX="${PREFIX:-$HOME/.local/bin}"
BASHRC="${BASHRC:-$HOME/.bashrc}"
BIN_NAME="vibe-sessions"
BEGIN_MARK="# >>> vibe-sessions >>>"
END_MARK="# <<< vibe-sessions <<<"

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_file="$here/$BIN_NAME"

with_bashrc=1
uninstall=0
for arg in "$@"; do
    case "$arg" in
        --no-bashrc) with_bashrc=0 ;;
        --uninstall) uninstall=1 ;;
        -h|--help) sed -n '2,7p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "install.sh: unknown option $arg" >&2; exit 2 ;;
    esac
done

strip_block() {
    [ -f "$BASHRC" ] || return 0
    grep -qF "$BEGIN_MARK" "$BASHRC" || return 0
    cp "$BASHRC" "$BASHRC.bak.vibe-sessions"
    awk -v begin="$BEGIN_MARK" -v end="$END_MARK" '
        $0 == begin { skip = 1; next }
        $0 == end   { skip = 0; next }
        !skip
    ' "$BASHRC.bak.vibe-sessions" > "$BASHRC"
    echo "removed the shell block from $BASHRC (backup: $BASHRC.bak.vibe-sessions)"
}

if [ "$uninstall" -eq 1 ]; then
    rm -f "$PREFIX/$BIN_NAME"
    echo "removed $PREFIX/$BIN_NAME"
    strip_block
    echo "Open a new shell (or run: source $BASHRC) to finish."
    exit 0
fi

# --- the command ---------------------------------------------------------- #

[ -f "$source_file" ] || { echo "install.sh: $source_file not found" >&2; exit 1; }
mkdir -p "$PREFIX"
chmod +x "$source_file"
ln -sfn "$source_file" "$PREFIX/$BIN_NAME"
echo "linked $PREFIX/$BIN_NAME -> $source_file"

case ":$PATH:" in
    *":$PREFIX:"*) ;;
    *) echo "warning: $PREFIX is not on your PATH" >&2 ;;
esac

# --- the shell block ------------------------------------------------------ #

if [ "$with_bashrc" -eq 1 ]; then
    strip_block
    cat >> "$BASHRC" <<'BLOCK'
# >>> vibe-sessions >>>
# Alt+V opens a picker of every Vibe session, across all folders.
# `vibe -s` does the same; every other `vibe` call passes straight through.
vibe() {
    if [ "$1" = "-s" ] || [ "$1" = "--sessions" ]; then
        shift
        command vibe-sessions "$@"
    else
        command vibe "$@"
    fi
}
bind -x '"\ev": vibe-sessions </dev/tty'
# <<< vibe-sessions <<<
BLOCK
    echo "added the Alt+V binding and the \`vibe -s\` wrapper to $BASHRC"
    echo "Open a new shell (or run: source $BASHRC) to pick them up."
else
    echo "skipped the shell block (--no-bashrc)"
fi
