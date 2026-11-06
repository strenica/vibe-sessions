# vibe-sessions

Browse and resume **every** [Mistral Vibe](https://github.com/mistralai/mistral-vibe) session, across all folders, from one table.

Vibe's own `/resume` picker is scoped to the folder you launched it from — sessions started in `~/work/api` are invisible from `~/work/web`. This reads the session store directly, so you get one list of everything, with a preview pane and a resume action.

```
┌ vibe sessions ─────────────────────────────────────────────────────────────┐
│ enter: resume   ctrl-y: copy id   esc: cancel                              │
│ ● 311b1b43    6m  Projects directory listing          ~/Desktop/projects   │
│ ○ 3984d2b0   12m  Mistral Vibe CLI architecture       /tmp/test            │
│ ○ 7f21c9aa    3h  Fix the tmux status bar             ~/dotfiles           │
└────────────────────────────────────────────────────────────────────────────┘
```

`●` marks a session a live process currently holds open.

## Install

```bash
./install.sh
```

That symlinks `vibe-sessions` into `~/.local/bin` and appends a marked block to `~/.bashrc`:

```bash
vibe() {
    if [ "$1" = "-s" ] || [ "$1" = "--sessions" ]; then
        shift
        command vibe-sessions "$@"
    else
        command vibe "$@"
    fi
}
bind -x '"\ev": vibe-sessions </dev/tty'
```

Open a new shell, then:

- **`vibe -s`** — open the picker
- **`Alt+V`** — open the picker from anywhere, without touching the command line you were typing

Every other `vibe` invocation passes straight through to the real binary.

Options: `--no-bashrc` installs the command only, `--uninstall` removes both, and `PREFIX` / `BASHRC` override the targets.

## Usage

```
vibe-sessions                 fuzzy picker; Enter resumes the selection
vibe-sessions --list          plain table
vibe-sessions --json          machine-readable, for scripts
vibe-sessions --folder        only sessions from the current directory
vibe-sessions --all           include archived sessions
vibe-sessions --limit 10      most recent N
vibe-sessions --filter tmux   non-interactive fuzzy match
vibe-sessions --preview ID    detail view for one session
```

Resuming changes into the session's original folder first, so the agent gets the right project context. `--no-cd` keeps you where you are, `--print` shows the command instead of running it, and `--exec` replaces the shell process instead of running Vibe as a child.

In the picker: `Enter` resumes, `Ctrl+Y` copies the session ID, `Esc` cancels. Typing filters on title, folder, and session ID.

## How it reads the store

Sessions live under `$VIBE_HOME/logs/session/` (default `~/.vibe`), honouring `session_logging.save_dir` from `config.toml`:

| Path | Used for |
|---|---|
| `unified/<id>/meta.json` | title, folder, model, branch, timestamps, archived flag |
| `unified/<id>/journal/*.jsonl` | last `set_envelope` → preview text, status, token usage; tail entries → recent messages |
| `active/<id>.lock.json` | live PID, for the running marker |

The journal is read newest-first and stops as soon as it has what it needs, so listing stays fast even with large session logs. The older `<root>/<id>/` layout is scanned too.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The suite builds a synthetic session store in a temp directory and exercises listing, ordering, folder filtering, archived handling, the running marker, JSON output, previews, and resume-command construction. No Vibe install or real sessions required.

## Notes

- Python 3.11+ (uses `tomllib` when available; falls back cleanly on older versions).
- `fzf` is optional — without it you get a numbered menu.
- Read-only: the tool never writes to the session store.
