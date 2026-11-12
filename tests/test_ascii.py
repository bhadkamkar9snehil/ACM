"""ASCII-only rule for ACM source, tests and the project manifest."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKED_SUFFIXES = {".py", ".toml", ".md", ".txt", ".yml", ".yaml"}


def _iter_checked():
    yield REPO_ROOT / "pyproject.toml"
    for tree in (REPO_ROOT / "src", REPO_ROOT / "tests"):
        yield from tree.rglob("*")


def test_acm_tree_is_ascii():
    offenders = []
    for path in _iter_checked():
        if path.suffix not in CHECKED_SUFFIXES or not path.is_file():
            continue
        data = path.read_bytes()
        for lineno, line in enumerate(data.splitlines(), start=1):
            bad = [byte for byte in line if byte > 127]
            if bad:
                offenders.append(
                    f"{path}:{lineno} non-ASCII bytes {bad[:5]}"
                )
                break
    assert not offenders, "\n".join(offenders)
