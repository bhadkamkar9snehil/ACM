"""ASCII-only rule, CI-enforced for the acm2 tree (standing rule)."""

from pathlib import Path

ACM2_ROOT = Path(__file__).resolve().parents[1]
CHECKED_SUFFIXES = {".py", ".toml", ".md", ".txt", ".yml", ".yaml"}


def test_acm2_tree_is_ascii():
    offenders = []
    for path in ACM2_ROOT.rglob("*"):
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
