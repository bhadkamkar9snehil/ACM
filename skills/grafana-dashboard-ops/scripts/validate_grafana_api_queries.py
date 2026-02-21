from __future__ import annotations

import json
import argparse
import time
from pathlib import Path
from typing import Dict, List, Tuple

import requests


REPO_ROOT = Path(__file__).resolve().parents[3]
ACTIVE_DASHBOARD_ROOT = REPO_ROOT / "install" / "observability" / "dashboards" / "active"
GRAFANA_URL = "http://localhost:3000"
AUTH_HEADER = {"Authorization": "Basic YWRtaW46YWRtaW4="}


def _load_dashboards() -> List[Tuple[Path, Dict]]:
    dashboards: List[Tuple[Path, Dict]] = []
    for path in sorted(ACTIVE_DASHBOARD_ROOT.rglob("*.json")):
        with path.open(encoding="utf-8-sig") as f:
            dashboards.append((path, json.load(f)))
    return dashboards


def _substitute_vars(sql: str) -> str:
    return (
        sql.replace("$equipment", "1")
        .replace("${equipment}", "1")
        .replace("$equip_id", "1")
        .replace("${equip_id}", "1")
        .replace("$equipment_code", "'FD_FAN'")
        .replace("${equipment_code}", "'FD_FAN'")
    )


def _run_query(raw_sql: str, ref_id: str, fmt: str, timeout: int) -> Tuple[bool, str]:
    payload = {
        "queries": [
            {
                "refId": ref_id,
                "datasource": {"uid": "mssql-ds", "type": "mssql"},
                "rawSql": _substitute_vars(raw_sql),
                "format": fmt,
                "intervalMs": 60000,
                "maxDataPoints": 500,
            }
        ],
        "from": "1704067200000",
        "to": "1893456000000",
    }

    last_error = ""
    resp = None
    for attempt in range(3):
        try:
            resp = requests.post(
                f"{GRAFANA_URL}/api/ds/query",
                headers=AUTH_HEADER,
                json=payload,
                timeout=timeout,
            )
            break
        except requests.RequestException as e:
            last_error = str(e)
            if attempt < 2:
                time.sleep(1)

    if resp is None:
        return False, f"request error {last_error[:220]}"

    if resp.status_code != 200:
        return False, f"http {resp.status_code} {resp.text[:220]}"

    data = resp.json()
    status = (((data.get("results") or {}).get(ref_id) or {}).get("status"))
    if status != 200:
        err = (((data.get("results") or {}).get(ref_id) or {}).get("error"))
        return False, f"status {status} error={str(err)[:220]}"
    return True, ""


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Validate active ACM dashboard SQL through Grafana API.")
    ap.add_argument("--timeout-sec", type=int, default=60, help="Per-query timeout in seconds.")
    return ap.parse_args()


def main() -> int:
    args = _parse_args()
    dashboards = _load_dashboards()
    errors: List[str] = []
    checked = 0

    for path, payload in dashboards:
        rel = path.relative_to(REPO_ROOT).as_posix()
        for panel in payload.get("panels", []):
            panel_id = panel.get("id")
            panel_title = panel.get("title", "")
            for target in panel.get("targets", []):
                raw_sql = target.get("rawSql")
                if not raw_sql:
                    continue
                checked += 1
                ref_id = target.get("refId", "A")
                fmt = target.get("format", "table")
                ok, msg = _run_query(raw_sql, ref_id, fmt, args.timeout_sec)
                if not ok:
                    errors.append(
                        f"{rel} panel={panel_id} ref={ref_id} title='{panel_title}' {msg}"
                    )

    if errors:
        print(f"Grafana API validation failed: checked={checked} errors={len(errors)}")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(f"Grafana API validation passed: checked={checked} errors=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
