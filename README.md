# vibe-sessions

Browse and resume **every** [Mistral Vibe](https://github.com/mistralai/mistral-vibe) session, across all folders, from one table.

Vibe's own `/resume` picker is scoped to the folder you launched it from — sessions started in `~/work/api` are invisible from `~/work/web`. This reads the session store directly, so you get one list of everything, with a preview pane and a resume action.

```
┌ vibe sessions ─────────────────────────────────────────────────────────────┐
│ enter: resume   ctrl-y: copy id   ctrl-x / right-click: delete   esc: cancel│
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
VIBE_SESSIONS_KEY='\ev'
bind -x "\"${VIBE_SESSIONS_KEY}\": vibe-sessions </dev/tty"
```

Open a new shell (or `source ~/.bashrc`), then press **Alt+V** — from anywhere, including mid-command, without disturbing the line you were typing.

### Remapping the key

Edit `VIBE_SESSIONS_KEY` in `~/.bashrc` and re-open your shell, or re-run the installer:

```bash
./install.sh --key '\C-g'
```

| Key | Value |
|---|---|
| Alt+V | `\ev` |
| Alt+F | `\ef` |
| Ctrl+G | `\C-g` |
| Ctrl+X then Ctrl+S | `\C-x\C-s` |
| Ctrl+Right | `\e[1;5C` |

Options: `--key` picks the binding, `--no-bashrc` installs the command only, `--uninstall` removes both, and `PREFIX` / `BASHRC` override the targets.

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
vibe-sessions --delete ID     delete a session (asks first)
```

Resuming changes into the session's original folder first, so the agent gets the right project context. `--no-cd` keeps you where you are, `--print` shows the command instead of running it, and `--exec` replaces the shell process instead of running Vibe as a child.

In the picker: `Enter` resumes, `Ctrl+Y` copies the session ID, `Esc` cancels. Typing filters on title, folder, and session ID.

## Deleting sessions

`Ctrl+X` — or a **right-click** on a row — asks for confirmation in a box, then removes the session and reloads the list. The box defaults to **No**, so a stray Enter never deletes anything.

```
┌┤ Delete session ├──────────────────────────────────────────┐
│ Delete this session?                                      │
│                                                           │
│ Fix the tmux status bar                                   │
│ /home/prep/dotfiles                                       │
│                                                           │
│ The session directory is removed permanently.             │
│                                                           │
│              <No>              <Yes>                      │
└───────────────────────────────────────────────────────────┘
```

Deleting removes the session directory plus the lock file and `continue-pointers` entry that reference it. A session that a live Vibe process still holds open is refused — close it first. The same flow is available non-interactively as `vibe-sessions --delete <id>` (add `--force` to skip the prompt).

Right-click is bound to delete, which replaces fzf's default right-click multi-select; this tool doesn't use multi-select.

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

The suite builds a synthetic session store in a temp directory and exercises listing, ordering, folder filtering, archived handling, the running marker, JSON output, previews, resume-command construction, and deletion (including the refusal to delete a running session and the refusal to delete without confirmation). No Vibe install or real sessions required.

## Notes

- Python 3.11+ (uses `tomllib` when available; falls back cleanly on older versions).
- `fzf` is optional — without it you get a numbered menu.
- Read-only apart from `--delete`, which removes a session directory and its bookkeeping after confirmation.
