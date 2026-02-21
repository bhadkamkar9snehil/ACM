from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple


REPO_ROOT = Path(__file__).resolve().parents[3]

# Grafana 12 allowed palette IDs observed in runtime error message.
ALLOWED_MODES = {
    "fixed",
    "shades",
    "thresholds",
    "palette-classic",
    "palette-classic-by-name",
    "continuous-GrYlRd",
    "continuous-RdYlGr",
    "continuous-BlYlRd",
    "continuous-YlRd",
    "continuous-BlPu",
    "continuous-YlBl",
    "continuous-blues",
    "continuous-reds",
    "continuous-greens",
    "continuous-purples",
}


def _iter_dashboard_files(active_only: bool) -> List[Path]:
    if active_only:
        roots = [
            REPO_ROOT / "install" / "observability" / "dashboards" / "active",
            REPO_ROOT / "grafana_dashboards" / "active",
        ]
    else:
        roots = [
            REPO_ROOT / "install" / "observability" / "dashboards",
            REPO_ROOT / "grafana_dashboards",
        ]
    files: List[Path] = []
    for root in roots:
        if root.exists():
            files.extend(sorted(root.rglob("*.json")))
    return files


def _check_file(path: Path) -> List[str]:
    issues: List[str] = []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    for panel in data.get("panels", []):
        panel_id = panel.get("id")
        panel_title = panel.get("title", "")
        color = ((panel.get("fieldConfig") or {}).get("defaults") or {}).get("color")
        if not isinstance(color, dict):
            continue
        mode = color.get("mode")
        if isinstance(mode, str) and mode and mode not in ALLOWED_MODES:
            issues.append(
                f"{path.relative_to(REPO_ROOT).as_posix()} panel={panel_id} title='{panel_title}' invalid_mode='{mode}'"
            )
    return issues


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Validate Grafana palette modes in ACM dashboards.")
    ap.add_argument(
        "--active-only",
        action="store_true",
        default=True,
        help="Check only active dashboards (default true).",
    )
    return ap.parse_args()


def main() -> int:
    args = _parse_args()
    files = _iter_dashboard_files(active_only=args.active_only)
    issues: List[str] = []
    for path in files:
        issues.extend(_check_file(path))

    if issues:
        print(f"Palette validation failed: issues={len(issues)}")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print(f"Palette validation passed: files={len(files)} issues=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
