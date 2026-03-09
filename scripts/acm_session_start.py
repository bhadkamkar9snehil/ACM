#!/usr/bin/env python3
"""
ACM Session Start — run this at the beginning of every Claude Code session.

What it does:
1. Rebuilds the Obsidian graph from current core/*.py (fast, ~2s)
2. Syncs the agent skill references so Claude can read them
3. Prints a session briefing: last version, modules changed since last refresh,
   knowledge notes available

Usage:
    python scripts/acm_session_start.py

Claude Code alias (add to CLAUDE.md or run manually):
    python scripts/acm_session_start.py && cat skills/acm-codebase-memory/references/00_Agent-Memory-Hub.md
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_REF_DIR = REPO_ROOT / "skills" / "acm-codebase-memory" / "references"
VAULT_DIR = REPO_ROOT / "docs" / "obsidian_vault"
KNOWLEDGE_DIR = VAULT_DIR / "knowledge"
VERSION_FILE = REPO_ROOT / "utils" / "version.py"


def _get_version() -> str:
    try:
        text = VERSION_FILE.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "__version__" in line and "=" in line:
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "unknown"


def _get_last_refresh() -> str:
    last_refresh = VAULT_DIR / "agent_memory" / "last_refresh.json"
    if last_refresh.exists():
        try:
            data = json.loads(last_refresh.read_text())
            return data.get("generated_at", "never")
        except Exception:
            pass
    return "never"


def _rebuild_graph() -> bool:
    script = REPO_ROOT / "scripts" / "build_acm_obsidian_graph.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"  OK{result.stdout.strip()}")
        return True
    else:
        print(f"  FAILGraph build failed: {result.stderr[:200]}")
        return False


def _sync_skill() -> bool:
    script = REPO_ROOT / "scripts" / "manage_acm_agent_memory.py"
    result = subprocess.run(
        [sys.executable, str(script), "refresh", "--sync-repo-skill"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        for line in result.stdout.strip().splitlines():
            print(f"  OK{line}")
        return True
    else:
        print(f"  FAILSkill sync failed: {result.stderr[:200]}")
        return False


def _list_knowledge_notes() -> list[str]:
    if not KNOWLEDGE_DIR.exists():
        return []
    return sorted(p.stem for p in KNOWLEDGE_DIR.glob("*.md"))


def _get_recent_commits(n: int = 5) -> list[str]:
    result = subprocess.run(
        ["git", "log", "--oneline", f"-{n}"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip().splitlines()
    return []


def main() -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    version = _get_version()
    prev_refresh = _get_last_refresh()

    print(f"\n{'='*60}")
    print(f"  ACM Session Start  {now}")
    print(f"  Version: {version}")
    print(f"  Previous graph refresh: {prev_refresh}")
    print(f"{'='*60}\n")

    print("[1/2] Rebuilding Obsidian knowledge graph...")
    _rebuild_graph()

    print("[2/2] Syncing agent skill references...")
    _sync_skill()

    print("\n--Knowledge Notes Available --")
    for note in _list_knowledge_notes():
        print(f"  [[knowledge/{note}]]")

    print("\n--Recent Commits --")
    for commit in _get_recent_commits():
        print(f"  {commit}")

    print("\n--Quick Reference --")
    print("  Entry point:    core/acm.py")
    print("  Batch runner:   scripts/sql_batch_runner.py")
    print("  Vault home:     docs/obsidian_vault/00_Home.md")
    print("  Agent hub:      skills/acm-codebase-memory/references/00_Agent-Memory-Hub.md")
    print("")
    print("  After any code change, update the relevant knowledge/ note.")
    print("  After any commit, re-run this script.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
