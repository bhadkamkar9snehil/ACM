"""ASCII-only rule, CI-enforced for the ACM2-owned trees (standing rule).

Scope after the #94 promotion (repo root IS the project): src/, tests/,
and the root pyproject - NOT lab/ (legacy, has its own history), docs/,
or paper/ (prose, em-dashes allowed there by their own conventions).
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKED_SUFFIXES = {".py", ".toml", ".md", ".txt", ".yml", ".yaml"}


def _iter_checked():
    yield REPO_ROOT / "pyproject.toml"
    for tree in (REPO_ROOT / "src", REPO_ROOT / "tests"):
        yield from tree.rglob("*")


def test_acm2_tree_is_ascii():
    offenders = []
    for path in _iter_checked():
        if path.suffix not in CHECKED_SUFFIXES or not path.is_file():
            continue
        if ".venv" in path.parts or "uv.lock" in path.name:
            continue
        data = path.read_bytes()
        for lineno, line in enumerate(data.splitlines(), start=1):
            bad = [b for b in line if b > 127]
            if bad:
                offenders.append(f"{path}:{lineno} non-ASCII bytes {bad[:5]}")
                break
    assert not offenders, "\n".join(offenders)
