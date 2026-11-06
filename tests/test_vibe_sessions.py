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
        env = dict(os.environ, VIBE_HOME=str(self.home))
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
        env = dict(os.environ, VIBE_HOME=str(empty))
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


if __name__ == "__main__":
    unittest.main()
