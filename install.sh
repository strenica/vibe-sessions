#!/usr/bin/env bash
# Install vibe-sessions: put it on PATH and bind a key to the picker.
#
#   ./install.sh                 install to ~/.local/bin, bind Alt+V
#   ./install.sh --key '\C-g'    bind a different key
#   ./install.sh --no-bashrc     install the command only
#   ./install.sh --uninstall     remove the command and the shell block
set -euo pipefail

PREFIX="${PREFIX:-$HOME/.local/bin}"
BASHRC="${BASHRC:-$HOME/.bashrc}"
BIN_NAME="vibe-sessions"
BEGIN_MARK="# >>> vibe-sessions >>>"
END_MARK="# <<< vibe-sessions <<<"
DEFAULT_KEY='\ev'

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_file="$here/$BIN_NAME"

with_bashrc=1
uninstall=0
key="$DEFAULT_KEY"
while [ $# -gt 0 ]; do
    case "$1" in
        --no-bashrc) with_bashrc=0 ;;
        --uninstall) uninstall=1 ;;
        --key) shift; key="${1:-}" ;;
        --key=*) key="${1#--key=}" ;;
        -h|--help) sed -n '2,7p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "install.sh: unknown option $1" >&2; exit 2 ;;
    esac
    shift
done

[ -n "$key" ] || { echo "install.sh: --key needs a value" >&2; exit 2; }

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
    block=$(cat <<'BLOCK'
# >>> vibe-sessions >>>
# Opens a picker of every Vibe session, across all folders.
# To remap, change VIBE_SESSIONS_KEY below and re-open your shell:
#   \ev        Alt+V            \C-g       Ctrl+G
#   \ef        Alt+F            \C-x\C-s   Ctrl+X then Ctrl+S
#   \e[1;5C    Ctrl+Right       \e[1;3C    Alt+Right
VIBE_SESSIONS_KEY='__KEY__'
bind -x "\"${VIBE_SESSIONS_KEY}\": vibe-sessions </dev/tty"
# <<< vibe-sessions <<<
BLOCK
)
    block=${block//__KEY__/$key}
    printf '%s\n' "$block" >> "$BASHRC"
    echo "bound $key to vibe-sessions in $BASHRC"
    echo "Open a new shell (or run: source $BASHRC) to pick it up."
else
    echo "skipped the shell block (--no-bashrc)"
fi
