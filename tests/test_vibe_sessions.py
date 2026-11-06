#!/usr/bin/env python3
"""Tests for vibe-sessions, run against a synthetic session store.

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "vibe-sessions"


def write_session(
    root: Path,
    session_id: str,
    *,
    title: str,
    directory: str,
    bumped: str,
    archived: bool = False,
    preview: str = "first question",
    messages: list[tuple[str, str]] | None = None,
    pid: int | None = None,
) -> Path:
    """Create one session directory in the unified store layout."""
    session_dir = root / "logs" / "session" / "unified" / session_id
    (session_dir / "journal").mkdir(parents=True, exist_ok=True)

    meta = {
        "session_id": session_id,
        "title": title,
        "title_source": "auto",
        "origin_directory": directory,
        "start_time": bumped,
        "bumped_at": bumped,
        "archived_at": bumped if archived else None,
        "config": {"active_model": "test-model", "model_name": "test-model-v1"},
        "environment": {"working_directory": directory},
        "child_sessions": [],
        "git_branch": "main",
    }
    (session_dir / "meta.json").write_text(json.dumps(meta))

    records = [
        {
            "type": "projection_delta",
            "payload": {
                "delta": [
                    {
                        "op": "set_envelope",
                        "state": {
                            "session": {
                                "id": session_id,
                                "title": title,
                                "preview": preview,
                                "status": {"type": "idle"},
                                "tokenUsage": {"totalTokens": 12345, "cachedInputTokens": 6000},
                                "updatedAt": 1794000000000,
                            }
                        },
                    }
                ]
            },
        }
    ]
    for index, (role, text) in enumerate(messages or []):
        records.append(
            {
                "type": "projection_delta",
                "payload": {
                    "delta": [
                        {
                            "op": "append_entry",
                            "entry": {
                                "id": f"entry-{index}",
                                "role": role,
                                "content": [{"type": "text", "text": text}],
                                "createdAt": 1794000000000 + index,
                            },
                        }
                    ]
                },
            }
        )
    (session_dir / "journal" / "0000000000000001.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n"
    )

    if pid is not None:
        active = root / "logs" / "session" / "active"
        active.mkdir(parents=True, exist_ok=True)
        (active / f"{session_id}.lock.json").write_text(
            json.dumps({"session_id": session_id, "process_id": pid, "lease_version": 1})
        )
    return session_dir


class VibeSessionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.workdir = self.home / "work"
        self.workdir.mkdir()

        write_session(
            self.home,
            "aaaaaaaa-1111-2222-3333-444444444444",
            title="Fix the tmux bar",
            directory=str(self.workdir),
            bumped="2026-11-06T10:00:00+00:00",
            messages=[("user", "the tmux bar is red"), ("assistant", "fixed the prefix colour")],
            pid=os.getpid(),
        )
        write_session(
            self.home,
            "bbbbbbbb-1111-2222-3333-444444444444",
            title="Scrape the catalogue",
            directory="/tmp/elsewhere",
            bumped="2026-11-05T10:00:00+00:00",
            messages=[("user", "scrape it"), ("assistant", "done")],
        )
        write_session(
            self.home,
            "cccccccc-1111-2222-3333-444444444444",
            title="Old archived thing",
            directory="/tmp/old",
            bumped="2026-10-01T10:00:00+00:00",
            archived=True,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_tool(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        env = dict(
            os.environ,
            VIBE_HOME=str(self.home),
            XDG_STATE_HOME=str(self.home / "state"),
        )
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(cwd or self.workdir),
        )

    # -- listing ---------------------------------------------------------- #

    def test_list_shows_sessions_newest_first(self) -> None:
        result = self.run_tool("--list", "--no-color")
        self.assertEqual(result.returncode, 0, result.stderr)
        out = result.stdout
        self.assertIn("Fix the tmux bar", out)
        self.assertIn("Scrape the catalogue", out)
        self.assertLess(out.index("Fix the tmux bar"), out.index("Scrape the catalogue"))

    def test_archived_hidden_by_default(self) -> None:
        self.assertNotIn("Old archived thing", self.run_tool("--list", "--no-color").stdout)
        self.assertIn("Old archived thing", self.run_tool("--list", "--all", "--no-color").stdout)

    def test_running_marker_uses_live_pid(self) -> None:
        out = self.run_tool("--list", "--no-color").stdout
        running = next(line for line in out.splitlines() if "Fix the tmux bar" in line)
        idle = next(line for line in out.splitlines() if "Scrape the catalogue" in line)
        self.assertTrue(running.startswith("●"), running)
        self.assertTrue(idle.startswith("○"), idle)

    def test_folder_filter(self) -> None:
        out = self.run_tool("--list", "--folder", "--no-color").stdout
        self.assertIn("Fix the tmux bar", out)
        self.assertNotIn("Scrape the catalogue", out)

    def test_limit(self) -> None:
        out = self.run_tool("--list", "--limit", "1", "--no-color").stdout
        self.assertIn("Fix the tmux bar", out)
        self.assertNotIn("Scrape the catalogue", out)

    def test_empty_store(self) -> None:
        empty = self.home / "empty"
        empty.mkdir()
        env = dict(os.environ, VIBE_HOME=str(empty), XDG_STATE_HOME=str(self.home / "state"))
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--list"], capture_output=True, text=True, env=env
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("No sessions found", result.stderr)

    # -- json ------------------------------------------------------------- #

    def test_json_shape(self) -> None:
        payload = json.loads(self.run_tool("--json").stdout)
        self.assertEqual(len(payload), 2)
        first = payload[0]
        self.assertEqual(first["id"], "aaaaaaaa-1111-2222-3333-444444444444")
        self.assertEqual(first["short"], "aaaaaaaa")
        self.assertEqual(first["title"], "Fix the tmux bar")
        self.assertEqual(first["directory"], str(self.workdir))
        self.assertEqual(first["pid"], os.getpid())
        self.assertEqual(first["model"], "test-model")

    # -- preview ---------------------------------------------------------- #

    def test_preview_shows_metadata_and_messages(self) -> None:
        result = self.run_tool("--preview", "aaaaaaaa")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Fix the tmux bar", result.stdout)
        self.assertIn(str(self.workdir), result.stdout)
        self.assertIn("test-model", result.stdout)
        self.assertIn("running (pid", result.stdout)
        self.assertIn("the tmux bar is red", result.stdout)
        self.assertIn("fixed the prefix colour", result.stdout)

    def test_preview_unknown_id(self) -> None:
        result = self.run_tool("--preview", "nope")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no session", result.stderr)

    # -- selection -------------------------------------------------------- #

    def test_filter_matches_title(self) -> None:
        out = self.run_tool("--filter", "tmux").stdout
        self.assertIn("Fix the tmux bar", out)
        self.assertNotIn("Scrape", out)

    def test_filter_no_match(self) -> None:
        self.assertEqual(self.run_tool("--filter", "zzzzz").returncode, 130)

    def test_print_builds_resume_command(self) -> None:
        out = self.run_tool("--filter", "tmux", "--print").stdout.strip()
        self.assertEqual(
            out,
            f"cd {self.workdir} && vibe --resume aaaaaaaa-1111-2222-3333-444444444444",
        )

    def test_print_without_cd(self) -> None:
        out = self.run_tool("--filter", "tmux", "--print", "--no-cd").stdout.strip()
        self.assertEqual(out, "vibe --resume aaaaaaaa-1111-2222-3333-444444444444")

    # -- raw (the reload feed) -------------------------------------------- #

    def test_raw_lines_are_row_then_id(self) -> None:
        lines = [line for line in self.run_tool("--raw").stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 2)
        for line in lines:
            row, session_id = line.split("\t")
            self.assertRegex(session_id, r"^[0-9a-f-]{36}$")
            self.assertIn(session_id[:8], row)


    # -- rename ----------------------------------------------------------- #

    def test_rename_sets_a_manual_title(self) -> None:
        result = self.run_tool("--rename", "bbbbbbbb", "--title", "Scraper, renamed")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Scraper, renamed", self.run_tool("--list", "--no-color").stdout)

        meta = json.loads(
            (self.home / "logs/session/unified/bbbbbbbb-1111-2222-3333-444444444444/meta.json").read_text()
        )
        self.assertEqual(meta["title"], "Scraper, renamed")
        self.assertEqual(meta["title_source"], "manual")

    def test_rename_refuses_running_session(self) -> None:
        result = self.run_tool("--rename", "aaaaaaaa", "--title", "nope")
        self.assertEqual(result.returncode, 1)
        self.assertIn("running", result.stderr.lower())

    def test_rename_without_a_title_cancels_without_a_tty(self) -> None:
        """No tty means no input box, so the rename must cancel cleanly."""
        result = self.run_tool("--rename", "bbbbbbbb")
        self.assertEqual(result.returncode, 130)
        self.assertIn("Scrape the catalogue", self.run_tool("--list", "--no-color").stdout)

    def test_rename_rejects_empty_title(self) -> None:
        result = self.run_tool("--rename", "bbbbbbbb", "--title", "   ")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Scrape the catalogue", self.run_tool("--list", "--no-color").stdout)

    # -- tags ------------------------------------------------------------- #

    def test_tag_roundtrip(self) -> None:
        result = self.run_tool("--tag", "bbbbbbbb", "--tags", "work, urgent")
        self.assertEqual(result.returncode, 0, result.stderr)

        payload = json.loads(self.run_tool("--json").stdout)
        tagged = next(item for item in payload if item["short"] == "bbbbbbbb")
        self.assertEqual(tagged["tags"], ["work", "urgent"])

        out = self.run_tool("--list", "--no-color").stdout
        self.assertIn("#work", out)
        self.assertIn("#urgent", out)

    def test_tag_clears_with_empty_value(self) -> None:
        self.run_tool("--tag", "bbbbbbbb", "--tags", "work")
        self.run_tool("--tag", "bbbbbbbb", "--tags", "")
        payload = json.loads(self.run_tool("--json").stdout)
        tagged = next(item for item in payload if item["short"] == "bbbbbbbb")
        self.assertEqual(tagged["tags"], [])

    def test_tags_survive_a_rename(self) -> None:
        self.run_tool("--tag", "bbbbbbbb", "--tags", "keepme")
        self.run_tool("--rename", "bbbbbbbb", "--title", "Renamed")
        payload = json.loads(self.run_tool("--json").stdout)
        tagged = next(item for item in payload if item["short"] == "bbbbbbbb")
        self.assertEqual(tagged["tags"], ["keepme"])

    # -- sort ------------------------------------------------------------- #

    def test_default_sort_puts_running_first(self) -> None:
        out = self.run_tool("--list", "--no-color").stdout
        self.assertLess(out.index("Fix the tmux bar"), out.index("Scrape the catalogue"))

    def test_sort_by_title(self) -> None:
        out = self.run_tool("--list", "--all", "--sort", "title", "--no-color").stdout
        self.assertLess(out.index("Fix the tmux bar"), out.index("Old archived thing"))
        self.assertLess(out.index("Old archived thing"), out.index("Scrape the catalogue"))

    def test_sort_by_folder(self) -> None:
        out = self.run_tool("--list", "--all", "--sort", "folder", "--no-color").stdout
        # /tmp/elsewhere < /tmp/old < <workdir>
        self.assertLess(out.index("Scrape the catalogue"), out.index("Old archived thing"))

    def test_cycle_sort_walks_the_modes(self) -> None:
        seen = [self.run_tool("--cycle-sort").stdout.strip() for _ in range(4)]
        self.assertEqual(seen, ["recent", "title", "folder", "status"])

    def test_sort_preference_persists(self) -> None:
        self.run_tool("--sort", "title")
        out = self.run_tool("--list", "--all", "--no-color").stdout
        self.assertLess(out.index("Old archived thing"), out.index("Scrape the catalogue"))


    # -- robustness -------------------------------------------------------- #

    def test_resume_without_vibe_reports_cleanly(self) -> None:
        """A missing `vibe` binary must not surface as a traceback."""
        env = dict(
            os.environ,
            VIBE_HOME=str(self.home),
            XDG_STATE_HOME=str(self.home / "state"),
            PATH="/nonexistent",
        )
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            input="1\n",
            capture_output=True,
            text=True,
            env=env,
            cwd=str(self.workdir),
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("not on PATH", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_version_flag(self) -> None:
        result = self.run_tool("--version")
        self.assertEqual(result.returncode, 0)
        self.assertRegex(result.stdout.strip(), r"^vibe-sessions \d+\.\d+\.\d+$")

    # -- delete leftovers -------------------------------------------------- #

    def test_delete_removes_per_session_plugin_data(self) -> None:
        plugin_data = self.home / "logs/session/plugins/data/bbbbbbbb-1111-2222-3333-444444444444/vibe"
        plugin_data.mkdir(parents=True)
        (plugin_data / "state.json").write_text("{}")

        result = self.run_tool("--delete", "bbbbbbbb", "--force")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(
            (self.home / "logs/session/plugins/data/bbbbbbbb-1111-2222-3333-444444444444").exists()
        )

    # -- prune-config ------------------------------------------------------ #

    def write_config(self, entries: list[str]) -> Path:
        config = self.home / "config.toml"
        body = "[tools.bash]\nallowlist = [\n"
        body += "".join(f'    "{entry}",\n' for entry in entries)
        body += "]\n"
        config.write_text(body)
        return config

    def test_prune_config_removes_only_dead_sessions(self) -> None:
        live = "vibe-path:exact:/home/prep/.vibe/logs/session/unified/aaaaaaaa-1111-2222-3333-444444444444"
        dead = "vibe-path:exact:/home/prep/.vibe/logs/session/unified/99999999-1111-2222-3333-444444444444"
        config = self.write_config([live, dead, "git"])

        result = self.run_tool("--prune-config")
        self.assertEqual(result.returncode, 0, result.stderr)

        text = config.read_text()
        self.assertIn("aaaaaaaa-1111-2222-3333-444444444444", text)
        self.assertNotIn("99999999-1111-2222-3333-444444444444", text)
        self.assertIn('"git"', text)
        self.assertTrue((self.home / "config.toml.bak.vibe-sessions").is_file())

    def test_prune_config_dry_run_changes_nothing(self) -> None:
        dead = "vibe-path:exact:/home/prep/.vibe/logs/session/unified/99999999-1111-2222-3333-444444444444"
        config = self.write_config([dead])
        before = config.read_text()

        result = self.run_tool("--prune-config", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("would remove", result.stdout)
        self.assertEqual(config.read_text(), before)
        self.assertFalse((self.home / "config.toml.bak.vibe-sessions").exists())

    def test_prune_config_with_nothing_stale(self) -> None:
        live = "vibe-path:exact:/home/prep/.vibe/logs/session/unified/aaaaaaaa-1111-2222-3333-444444444444"
        config = self.write_config([live])
        before = config.read_text()

        result = self.run_tool("--prune-config")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no stale", result.stdout)
        self.assertEqual(config.read_text(), before)

    # -- delete ----------------------------------------------------------- #

    def test_delete_removes_directory_and_bookkeeping(self) -> None:
        session_dir = self.home / "logs/session/unified/bbbbbbbb-1111-2222-3333-444444444444"
        self.assertTrue(session_dir.is_dir())

        pointer = self.home / "logs/session/continue-pointers/deadbeef"
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_text("bbbbbbbb-1111-2222-3333-444444444444")

        result = self.run_tool("--delete", "bbbbbbbb", "--force")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(session_dir.exists())
        self.assertFalse(pointer.exists())
        self.assertNotIn("Scrape the catalogue", self.run_tool("--list", "--no-color").stdout)

    def test_delete_refuses_running_session(self) -> None:
        session_dir = self.home / "logs/session/unified/aaaaaaaa-1111-2222-3333-444444444444"
        result = self.run_tool("--delete", "aaaaaaaa", "--force")
        self.assertEqual(result.returncode, 1)
        self.assertIn("running", result.stderr.lower())
        self.assertTrue(session_dir.is_dir(), "a running session must survive")

    def test_delete_without_confirmation_keeps_session(self) -> None:
        # No tty in the test harness, so the confirmation cannot be answered.
        session_dir = self.home / "logs/session/unified/bbbbbbbb-1111-2222-3333-444444444444"
        result = self.run_tool("--delete", "bbbbbbbb")
        self.assertEqual(result.returncode, 130)
        self.assertTrue(session_dir.is_dir())

    def test_delete_unknown_id(self) -> None:
        result = self.run_tool("--delete", "nope", "--force")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no session", result.stderr)

    def test_delete_leaves_the_project_directory_untouched(self) -> None:
        """Deleting a session must never touch the folder it ran in."""
        project = self.home / "myproject"
        project.mkdir()
        (project / "main.py").write_text("print('hi')\n")
        (project / "data.txt").write_text("important\n")
        (project / "sub").mkdir()
        (project / "sub" / "nested.txt").write_text("also important\n")

        write_session(
            self.home,
            "dddddddd-1111-2222-3333-444444444444",
            title="Work in a project",
            directory=str(project),
            bumped="2026-11-04T10:00:00+00:00",
        )

        result = self.run_tool("--delete", "dddddddd", "--force")
        self.assertEqual(result.returncode, 0, result.stderr)

        session_dir = self.home / "logs/session/unified/dddddddd-1111-2222-3333-444444444444"
        self.assertFalse(session_dir.exists(), "the session directory should be gone")

        self.assertTrue((project / "main.py").is_file())
        self.assertTrue((project / "data.txt").is_file())
        self.assertTrue((project / "sub" / "nested.txt").is_file())
        self.assertEqual((project / "main.py").read_text(), "print('hi')\n")
        self.assertEqual((project / "data.txt").read_text(), "important\n")


if __name__ == "__main__":
    unittest.main()
