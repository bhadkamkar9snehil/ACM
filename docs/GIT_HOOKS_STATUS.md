# Git Hooks Status

Date: 2026-03-08

Current status:
- Local custom Git hooks are disabled for this repo for now.
- `core.hooksPath` is not configured.
- The only active custom hook that was present was `.git/hooks/post-commit`.
- It has been disabled by renaming it to `.git/hooks/post-commit.disabled`.

Hook that was present:

```sh
#!/bin/sh
# ACM post-commit hook: refresh Obsidian knowledge graph after every commit
# Only triggers when core/ files are changed.

REPO_ROOT="$(git rev-parse --show-toplevel)"

CHANGED=$(git diff-tree --no-commit-id -r --name-only HEAD | grep "^core/")
if [ -z "$CHANGED" ]; then
    exit 0
fi

echo "[ACM] core/ changed - refreshing Obsidian knowledge graph..."
cd "$REPO_ROOT" && python scripts/build_acm_obsidian_graph.py > /dev/null 2>&1 && \
    python scripts/manage_acm_agent_memory.py refresh > /dev/null 2>&1
echo "[ACM] Knowledge graph updated."
exit 0
```

What it did:
- Ran after each commit.
- If the commit touched `core/`, it attempted to rebuild the Obsidian graph and refresh ACM agent memory.

Why it was disabled:
- Git operations were showing inconsistent and unwanted behavior around commit completion and hook execution.
- A recent commit path emitted `fatal: cannot exec '.git/hooks/post-commit': No such file or directory`.
- The hook also depends on `python` being available on PATH, which is not consistently true in this environment.
- Until the hook behavior is investigated properly, it is safer to keep it disabled and run memory refresh manually when needed.

Manual replacement commands:

```sh
python3 scripts/build_acm_obsidian_graph.py
python3 scripts/manage_acm_agent_memory.py refresh --sync-repo-skill --sync-local-skill
python3 scripts/manage_acm_agent_memory.py health
```

How to re-enable later:
- Rename `.git/hooks/post-commit.disabled` back to `.git/hooks/post-commit`.
- Confirm `python` or `python3` availability in the shell used by Git hooks.
- Re-test with a trivial local commit before relying on it.
