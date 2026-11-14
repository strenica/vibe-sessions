# vibe-sessions

Browse and resume **every** [Mistral Vibe](https://github.com/mistralai/mistral-vibe) session, across all folders, from one table.

Vibe's own `/resume` picker is scoped to the folder you launched it from — sessions started in `~/work/api` are invisible from `~/work/web`. This reads the session store directly, so you get one list of everything, with a preview pane and a resume action.

```
┌ vibe sessions ─────────────────────────────────────────────────────────────┐
│ enter resume · ctrl-y copy id · ctrl-x delete · → / right-click menu · ctrl-s sort │
│ ● 311b1b43    6m  Projects directory listing      ~/Desktop/projects  #work  │
│ ○ 3984d2b0   12m  Mistral Vibe CLI architecture   /tmp/test                  │
│ ○ 7f21c9aa    3h  Fix the tmux status bar         ~/dotfiles          #dot   │
└────────────────────────────────────────────────────────────────────────────┘
```

`●` marks a session a live process currently holds open. Tags are shown in yellow.

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
vibe-sessions --rename ID     rename a session
vibe-sessions --tag ID        tag a session
vibe-sessions --sort MODE     status | recent | title | folder
vibe-sessions --prune-config  drop config.toml allowlist entries for dead sessions
vibe-sessions --grep PATTERN  only sessions whose conversation mentions PATTERN
```

Resuming changes into the session's original folder first, so the agent gets the right project context. `--no-cd` keeps you where you are, `--print` shows the command instead of running it, and `--exec` replaces the shell process instead of running Vibe as a child.

In the picker: `Enter` resumes, `Ctrl+Y` copies the session ID, `Ctrl+X` deletes, `Ctrl+S` cycles the sort order, `Esc` cancels. Typing filters on title, folder, tags, and session ID.

`→` opens the action menu, so the whole thing is usable without a mouse. It only does that while the search box is empty — once you start typing, `→` moves the cursor as usual.

## Searching transcripts

The picker filters on title, folder, tags, and ID — the row text. To find a session by *what was said in it*, use `--grep`:

```bash
vibe-sessions --grep "compaction threshold"
```

That opens the normal picker, restricted to sessions whose conversation mentions it, with the matching line shown dimmed at the end of each row and the surrounding context in the preview pane.

Inside the picker, **`Ctrl+G`** toggles the same search for whatever is currently in the search box. That's the rescue hatch: type `compaction`, get zero rows because no title contains it, press `Ctrl+G`, and the list refills with sessions that discussed it. The header switches to `SEARCHING TRANSCRIPTS` so you can tell which mode you're in. Press `Ctrl+G` again to go back.

**How it stays fast.** grep is C-speed and finds candidate journals in ~120 ms across a thousand sessions; JSON parsing is the expensive part. So grep shortlists, and only the files it flags get parsed. Measured on a synthetic 1000-session / 214 MB store:

| Approach | Time |
|---|---|
| `grep -rl` over every journal | 0.12 s |
| Parse every journal in Python | 1.50 s |
| grep to shortlist, then parse only the hits | 0.01 s |

It also means a hit in *tool output* doesn't count — grep flags the file, but the parse confirms the match is in something you or the assistant actually said, not a file the agent once read.

Two limits worth knowing: after `Ctrl+G`, typing narrows within the grep results rather than re-grepping (the snippet is the only content fzf can see), so press `Ctrl+G` again to re-run with a new query. And a query common enough to match every session degenerates to parsing everything — about 1.5 s at a thousand sessions.

## Sorting

The list is sorted by `status` by default: sessions a live process holds open come first, then most recently used. `Ctrl+S` cycles through the modes and remembers your choice; `--sort` sets it directly.

| Mode | Order |
|---|---|
| `status` | running first, then most recently used |
| `recent` | most recently used |
| `title` | alphabetical |
| `folder` | grouped by project folder |

## Managing sessions

**Right-click a row** — or press `→` with an empty search box — to open an action menu, the same idea as tmux's `display-menu`:

```
┌┤ Session ├──────────────────────────────────────────────────┐
│ Fix the tmux status bar                                    │
│ /home/prep/dotfiles                                        │
│ Tags: #dot                                                 │
│                                                            │
│   Rename this session                                      │
│   Tag this session                                         │
│   Delete this session                                      │
│   Cancel                                                   │
└────────────────────────────────────────────────────────────┘
```

`Ctrl+X` skips the menu and goes straight to delete.

### Rename

```bash
vibe-sessions --rename <id> --title "New name"
```

Writes `title` and `title_source = "manual"` into `meta.json` — the same fields Vibe's own `/rename` sets — **and** keeps a copy in the sidecar state file.

The copy is not redundant. Vibe builds its metadata with `title=session.title`, taken from the *in-memory* session, and on resume it seeds that from the journal envelope rather than from `meta.json`. So an external rename is reset the next time the session is used. The sidecar keeps your name visible in this picker; a manual title in `meta.json` — set by Vibe's own `/rename` — always wins over it.

The practical consequence: **a rename made here sticks in this tool, but not in Vibe.** If you want the name to hold everywhere, run `/rename` inside the session. Renaming a session a live process holds open is refused outright.

### Tag

Vibe has no notion of tags, so they live in a sidecar file this tool owns (`$XDG_STATE_HOME/vibe-sessions/state.json`). Keeping them out of `meta.json` means Vibe rewriting a session cannot drop them. Tags show in the table and are searchable in the picker.

```bash
vibe-sessions --tag <id> --tags "work,urgent"   # set
vibe-sessions --tag <id> --tags ""              # clear
```

### Delete

Asks for confirmation in a box that defaults to **No**, then removes the session and reloads the list.

```
┌┤ Delete session ├──────────────────────────────────────────┐
│ Delete this session?                                      │
│ Fix the tmux status bar                                   │
│ /home/prep/dotfiles                                       │
│ The session directory is removed permanently.             │
│   No                                                      │
│   Yes                                                     │
└───────────────────────────────────────────────────────────┘
```

Deleting removes the session directory, its lock file, the `continue-pointers` entry that references it, and its `plugins/data/<id>` directory. It never touches the folder the session ran in. A session a live Vibe process still holds open is refused — close it first.

One thing delete deliberately leaves alone: Vibe writes auto-approved paths into `config.toml` as `vibe-path:exact:.../unified/<id>` entries, and those outlive the session. They grant nothing once the directory is gone, but they accumulate. Clean them up explicitly, since `config.toml` is your file and not the tool's:

```bash
vibe-sessions --prune-config --dry-run   # show what would go
vibe-sessions --prune-config             # remove, with a backup
```

It only ever removes lines naming a session directory that no longer exists, and writes `config.toml.bak.vibe-sessions` first.

```bash
vibe-sessions --delete <id>          # asks first
vibe-sessions --delete <id> --force  # no prompt
```

Right-click is bound to the menu, which replaces fzf's default right-click multi-select; this tool doesn't use multi-select.

All three widgets — the action menu, the rename/tag input, and the delete confirmation — are fzf, not whiptail. whiptail does not understand modern key encodings such as CSI-u: it sees the ESC of a Ctrl+Backspace, quits, and the rest of the sequence leaks into the parent fzf as a search query, which empties the list. whiptail is only used when fzf is unavailable.

## How it reads the store

Sessions live under `$VIBE_HOME/logs/session/` (default `~/.vibe`), honouring `session_logging.save_dir` from `config.toml`:

| Path | Used for |
|---|---|
| `unified/<id>/meta.json` | title, folder, model, branch, timestamps, archived flag |
| `unified/<id>/journal/*.jsonl` | last `set_envelope` → preview text, status, token usage; tail entries → recent messages |
| `active/<id>.lock.json` | live PID, for the running marker |

The journal is read newest-first and stops as soon as it has what it needs, so listing stays fast even with large session logs. The older `<root>/<id>/` layout is scanned too.

Tags and the sort preference live outside the store, in `$XDG_STATE_HOME/vibe-sessions/state.json` (default `~/.local/state/vibe-sessions/state.json`), so Vibe rewriting a session cannot clobber them.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The suite builds a synthetic session store in a temp directory and exercises listing, ordering, folder filtering, archived handling, the running marker, JSON output, previews, resume-command construction, renaming, tagging, every sort mode, and deletion (including the refusal to delete a running session, the refusal to delete without confirmation, and the guarantee that the project folder is left untouched). No Vibe install or real sessions required.

## Notes

- Python 3.11+ (uses `tomllib` when available; falls back cleanly on older versions).
- `fzf` is optional — without it you get a numbered menu.
- Read-only apart from `--delete` (removes a session directory and its bookkeeping after confirmation), `--rename` (rewrites one field in `meta.json`), and `--prune-config` (removes stale allowlist lines from `config.toml`, with a backup).
- MIT licensed.
