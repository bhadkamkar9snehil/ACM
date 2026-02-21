from __future__ import annotations

import json
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.sql_client import SQLClient
ACTIVE_DASHBOARD_ROOT = REPO_ROOT / "install" / "observability" / "dashboards" / "active"
ALL_DASHBOARD_ROOT = REPO_ROOT / "install" / "observability" / "dashboards"


def _load_dashboards(include_archive: bool) -> List[Tuple[Path, Dict]]:
    root = ALL_DASHBOARD_ROOT if include_archive else ACTIVE_DASHBOARD_ROOT
    dashboards: List[Tuple[Path, Dict]] = []
    for path in sorted(root.rglob("*.json")):
        with path.open(encoding="utf-8-sig") as f:
            dashboards.append((path, json.load(f)))
    return dashboards


def _check_duplicate_uids(dashboards: List[Tuple[Path, Dict]]) -> List[str]:
    by_uid: Dict[str, List[Path]] = {}
    for path, payload in dashboards:
        uid = payload.get("uid")
        if not uid:
            continue
        by_uid.setdefault(uid, []).append(path)

    errors: List[str] = []
    for uid, paths in sorted(by_uid.items()):
        if len(paths) > 1:
            joined = ", ".join(p.relative_to(REPO_ROOT).as_posix() for p in paths)
            errors.append(f"duplicate uid '{uid}' in {joined}")
    return errors


def _iter_sql_targets(payload: Dict):
    for panel in payload.get("panels", []):
        panel_id = panel.get("id")
        panel_title = panel.get("title", "")
        for target in panel.get("targets", []):
            raw_sql = target.get("rawSql")
            if not raw_sql:
                continue
            yield panel_id, panel_title, target.get("refId", "?"), raw_sql


def _substitute_macros(sql: str) -> str:
    return (
        sql.replace("$__timeFrom()", "'2020-01-01T00:00:00'")
        .replace("$__timeTo()", "'2030-01-01T00:00:00'")
        .replace("$equipment", "1")
        .replace("${equipment}", "1")
        .replace("$equip_id", "1")
        .replace("${equip_id}", "1")
        .replace("$equipment_code", "'FD_FAN'")
        .replace("${equipment_code}", "'FD_FAN'")
    )


def _check_sql_targets(dashboards: List[Tuple[Path, Dict]]) -> List[str]:
    errors: List[str] = []
    cli = SQLClient.from_ini("acm")
    cli.connect()
    cur = cli.cursor()
    try:
        for path, payload in dashboards:
            for panel_id, panel_title, ref_id, raw_sql in _iter_sql_targets(payload):
                sql = _substitute_macros(raw_sql)
                try:
                    cur.execute(sql)
                    cur.fetchmany(1)
                except Exception as e:  # pragma: no cover - integration surface
                    rel = path.relative_to(REPO_ROOT).as_posix()
                    errors.append(
                        f"{rel} panel={panel_id} ref={ref_id} title='{panel_title}' error={str(e).splitlines()[0]}"
                    )
    finally:
        cli.close()
    return errors


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Validate ACM Grafana dashboards against SQL schema.")
    ap.add_argument(
        "--include-archive",
        action="store_true",
        help="Validate all dashboards under install/observability/dashboards, including archive.",
    )
    return ap.parse_args()


def main() -> int:
    args = _parse_args()
    dashboards = _load_dashboards(include_archive=args.include_archive)
    dup_errors = _check_duplicate_uids(dashboards)
    sql_errors = _check_sql_targets(dashboards)

    if dup_errors:
        print("Duplicate UID issues:")
        for err in dup_errors:
            print(f"  - {err}")
    if sql_errors:
        print("SQL target issues:")
        for err in sql_errors:
            print(f"  - {err}")

    if dup_errors or sql_errors:
        print(f"Validation failed: duplicate_uid={len(dup_errors)} sql_errors={len(sql_errors)}")
        return 1

    print("Validation passed: no duplicate UIDs and SQL targets executed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
