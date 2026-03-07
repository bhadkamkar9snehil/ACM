#!/usr/bin/env python3
"""
Agent-managed ACM memory pipeline.

This script keeps an Obsidian-backed memory graph and an agent skill memory pack
in sync so code-aware agents can load stable ACM context on demand.

Commands:
    refresh         rebuild graph and memory artifacts
    health          run memory integrity checks
    sync-repo-skill copy memory artifacts into repo skill references
    sync-local-skill copy repo skill into local CODEX_HOME skill folder
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = REPO_ROOT / "core"
OBSIDIAN_DIR = REPO_ROOT / "docs" / "obsidian_vault"
AGENT_MEMORY_DIR = OBSIDIAN_DIR / "agent_memory"
REPO_SKILL_DIR = REPO_ROOT / "skills" / "acm-codebase-memory"
REPO_SKILL_REF_DIR = REPO_SKILL_DIR / "references"

LOCAL_CODEX_HOME = Path(
    (Path.home() / ".codex").as_posix()
)
LOCAL_SKILL_DIR = LOCAL_CODEX_HOME / "skills" / "acm-codebase-memory"
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


@dataclass
class ModuleSnapshot:
    module_name: str
    source_path: str
    symbol_count: int
    core_imports: List[str]


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _module_name(py_path: Path) -> str:
    rel = py_path.relative_to(REPO_ROOT).as_posix()
    return rel[:-3].replace("/", ".")


def _iter_core_py() -> List[Path]:
    files = sorted(CORE_DIR.glob("*.py"))
    return [p for p in files if p.name != "__init__.py"]


def _resolve_core_imports(current_module: str, tree: ast.Module) -> Set[str]:
    imports: Set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("core."):
                    imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            level = int(getattr(node, "level", 0) or 0)
            module = node.module or ""
            if level == 0 and module.startswith("core"):
                imports.add(module)
                continue
            if level > 0:
                current_parts = current_module.split(".")
                if level > len(current_parts):
                    continue
                base_parts = current_parts[: len(current_parts) - level]
                if module:
                    base_parts = base_parts + module.split(".")
                for alias in node.names:
                    if alias.name == "*":
                        candidate = ".".join(base_parts)
                    else:
                        candidate_parts = list(base_parts)
                        if not module:
                            candidate_parts.append(alias.name)
                        candidate = ".".join(candidate_parts)
                    if candidate.startswith("core."):
                        imports.add(candidate)
    imports.discard(current_module)
    return imports


def _count_symbols(tree: ast.Module) -> int:
    symbol_count = 0
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbol_count += 1
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbol_count += 1
    return symbol_count


def _collect_snapshots() -> List[ModuleSnapshot]:
    snapshots: List[ModuleSnapshot] = []
    for py in _iter_core_py():
        src = py.read_text(encoding="utf-8-sig")
        tree = ast.parse(src, filename=str(py))
        mod = _module_name(py)
        imports = sorted(_resolve_core_imports(mod, tree))
        snapshots.append(
            ModuleSnapshot(
                module_name=mod,
                source_path=py.relative_to(REPO_ROOT).as_posix(),
                symbol_count=_count_symbols(tree),
                core_imports=imports,
            )
        )
    return sorted(snapshots, key=lambda x: x.module_name)


def _run_graph_builder() -> None:
    script = REPO_ROOT / "scripts" / "build_acm_obsidian_graph.py"
    cmd = [sys.executable, str(script)]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        raise RuntimeError(f"Graph build failed with code {proc.returncode}")
    print(proc.stdout.strip())


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _render_agent_hub(
    snapshots: List[ModuleSnapshot],
    generated_at: str,
) -> str:
    top = sorted(snapshots, key=lambda x: x.symbol_count, reverse=True)[:12]
    rows = "\n".join(
        f"- [[modules/{s.module_name}|{s.module_name}]] symbols={s.symbol_count}"
        for s in top
    ) or "- none"
    return f"""---
type: agent-memory
generated_at: {generated_at}
---

# ACM Agent Memory Hub

This note is generated for agent-first ACM context loading.

## Quick Start
1. Read `[[../00_Home]]`
2. Read `[[../01_Modules]]`
3. Read `[[../modules/core.acm]]`
4. Read `[[../modules/core.output_manager]]`
5. Read `[[../modules/core.run_metadata_writer]]`

## Highest Symbol Density Modules
{rows}

## Commands
1. Refresh memory:
`python scripts/manage_acm_agent_memory.py refresh --sync-repo-skill --sync-local-skill`
2. Health check:
`python scripts/manage_acm_agent_memory.py health`
"""


def _render_runtime_critical() -> str:
    return """---
type: agent-memory
---

# ACM Runtime Critical Path

Primary runtime file:
- [[../modules/core.acm|core.acm]]

Critical supporting ownership:
1. [[../modules/core.sql_client|core.sql_client]]
2. [[../modules/core.smart_coldstart|core.smart_coldstart]]
3. [[../modules/core.fast_features|core.fast_features]]
4. [[../modules/core.detector_orchestrator|core.detector_orchestrator]]
5. [[../modules/core.regimes|core.regimes]]
6. [[../modules/core.fuse|core.fuse]]
7. [[../modules/core.drift|core.drift]]
8. [[../modules/core.output_manager|core.output_manager]]
9. [[../modules/core.run_metadata_writer|core.run_metadata_writer]]
10. [[../modules/core.observability|core.observability]]
"""


def _render_ownership(snapshots: List[ModuleSnapshot]) -> str:
    lines: List[str] = [
        "---",
        "type: agent-memory",
        "---",
        "",
        "# ACM Module Ownership Snapshot",
        "",
        "| Module | Symbols | Core Imports |",
        "|---|---:|---:|",
    ]
    for s in sorted(snapshots, key=lambda x: (x.module_name, -x.symbol_count)):
        lines.append(f"| `[{s.module_name}]` | {s.symbol_count} | {len(s.core_imports)} |")
    return "\n".join(lines)


def _render_sql_map() -> str:
    return """---
type: agent-memory
---

# ACM SQL Output Map

Primary persistence owner:
- [[../modules/core.output_manager|core.output_manager]]

Primary run-finalization owner:
- [[../modules/core.run_metadata_writer|core.run_metadata_writer]]

Run lifecycle table:
1. ACM_Runs

Primary interpretation tables:
1. ACM_Scores_Wide
2. ACM_Episodes
3. ACM_HealthTimeline
4. ACM_DriftController
5. ACM_DataQuality
"""


def _write_memory_artifacts(snapshots: List[ModuleSnapshot], generated_at: str) -> None:
    AGENT_MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    _write_text(
        AGENT_MEMORY_DIR / "00_Agent-Memory-Hub.md",
        _render_agent_hub(snapshots, generated_at),
    )
    _write_text(
        AGENT_MEMORY_DIR / "01_Runtime-Critical-Path.md",
        _render_runtime_critical(),
    )
    _write_text(
        AGENT_MEMORY_DIR / "02_Module-Ownership.md",
        _render_ownership(snapshots),
    )
    _write_text(
        AGENT_MEMORY_DIR / "03_SQL-Output-Map.md",
        _render_sql_map(),
    )

    payload = {
        "generated_at": generated_at,
        "module_count": len(snapshots),
        "modules": [
            {
                "module_name": s.module_name,
                "source_path": s.source_path,
                "symbol_count": s.symbol_count,
                "core_import_count": len(s.core_imports),
                "core_imports": s.core_imports,
            }
            for s in snapshots
        ],
    }
    _write_text(AGENT_MEMORY_DIR / "memory_index.json", json.dumps(payload, indent=2))
    _write_text(
        AGENT_MEMORY_DIR / "last_refresh.json",
        json.dumps(
            {
                "generated_at": generated_at,
                "status": "ok",
                "module_count": len(snapshots),
            },
            indent=2,
        ),
    )


def _sync_repo_skill_references() -> int:
    sources = [
        OBSIDIAN_DIR / "00_Home.md",
        OBSIDIAN_DIR / "01_Modules.md",
        OBSIDIAN_DIR / "03_Runtime-Flow.md",
        OBSIDIAN_DIR / "04_Outputs-and-Status.md",
        AGENT_MEMORY_DIR / "00_Agent-Memory-Hub.md",
        AGENT_MEMORY_DIR / "01_Runtime-Critical-Path.md",
        AGENT_MEMORY_DIR / "02_Module-Ownership.md",
        AGENT_MEMORY_DIR / "03_SQL-Output-Map.md",
        AGENT_MEMORY_DIR / "memory_index.json",
    ]
    copied = 0
    for src in sources:
        if src.exists():
            _copy_file(src, REPO_SKILL_REF_DIR / src.name)
            copied += 1
    return copied


def _sync_local_skill() -> int:
    if not REPO_SKILL_DIR.exists():
        raise RuntimeError(f"Repo skill directory missing: {REPO_SKILL_DIR}")
    if LOCAL_SKILL_DIR.exists():
        shutil.rmtree(LOCAL_SKILL_DIR)
    shutil.copytree(REPO_SKILL_DIR, LOCAL_SKILL_DIR)
    return sum(1 for _ in LOCAL_SKILL_DIR.rglob("*"))


def _iter_link_check_files() -> List[Path]:
    # Link integrity is enforced for the canonical Obsidian vault graph.
    # Skill reference files are a compact subset and may contain intentional
    # links that only resolve inside the full vault.
    files: List[Path] = []
    files.extend(sorted(OBSIDIAN_DIR.rglob("*.md")))
    # De-duplicate while preserving order.
    dedup: List[Path] = []
    seen: Set[str] = set()
    for p in files:
        key = p.resolve().as_posix()
        if key in seen:
            continue
        seen.add(key)
        dedup.append(p)
    return dedup


def _split_wikilink_target(raw_target: str) -> str:
    target = raw_target.split("|", 1)[0].strip()
    target = target.split("#", 1)[0].strip()
    return target


def _candidate_note_paths(base_dir: Path, target: str) -> List[Path]:
    target_path = Path(target)
    has_explicit_md = target.lower().endswith(".md")
    cands: List[Path] = []
    if has_explicit_md:
        cands.append(base_dir / target_path)
    else:
        cands.append(base_dir / f"{target}.md")
    return cands


def _resolve_wikilink(source_file: Path, raw_target: str) -> bool:
    target = _split_wikilink_target(raw_target)
    if not target:
        return True
    if target.lower().startswith(("http://", "https://")):
        return True

    # Explicit path-like targets.
    if "/" in target or "\\" in target or target.startswith("."):
        candidates: List[Path] = []
        candidates.extend(_candidate_note_paths(source_file.parent, target))
        candidates.extend(_candidate_note_paths(OBSIDIAN_DIR, target))
        candidates.extend(_candidate_note_paths(REPO_SKILL_REF_DIR, target))
        return any(c.exists() for c in candidates)

    # Bare note names: allow unique match in known roots.
    candidate_name = target if target.endswith(".md") else f"{target}.md"
    hits: List[Path] = []
    hits.extend(OBSIDIAN_DIR.rglob(candidate_name))
    hits.extend(REPO_SKILL_REF_DIR.rglob(candidate_name))
    return len(hits) > 0


def _check_wikilinks() -> Dict[str, object]:
    files = _iter_link_check_files()
    broken_links: List[Dict[str, str]] = []
    total_links = 0

    for md in files:
        try:
            content = md.read_text(encoding="utf-8-sig")
        except Exception:
            continue
        for match in WIKILINK_RE.finditer(content):
            raw_target = match.group(1).strip()
            total_links += 1
            if not _resolve_wikilink(md, raw_target):
                broken_links.append(
                    {
                        "source": md.relative_to(REPO_ROOT).as_posix(),
                        "target": raw_target,
                    }
                )

    return {
        "files_scanned": len(files),
        "links_scanned": total_links,
        "broken_count": len(broken_links),
        "broken_links": broken_links[:200],
    }


def _health() -> Tuple[bool, Dict[str, object]]:
    required = [
        OBSIDIAN_DIR / "00_Home.md",
        OBSIDIAN_DIR / "01_Modules.md",
        OBSIDIAN_DIR / "02_Functions.md",
        AGENT_MEMORY_DIR / "00_Agent-Memory-Hub.md",
        AGENT_MEMORY_DIR / "memory_index.json",
        REPO_SKILL_DIR / "SKILL.md",
        REPO_SKILL_REF_DIR / "00_Agent-Memory-Hub.md",
    ]
    missing = [p.as_posix() for p in required if not p.exists()]
    link_report = _check_wikilinks()
    ok = len(missing) == 0 and int(link_report.get("broken_count", 0)) == 0
    details: Dict[str, object] = {
        "ok": ok,
        "missing": missing,
        "checked_files": [p.as_posix() for p in required],
        "link_check": link_report,
    }
    return ok, details


def cmd_refresh(args: argparse.Namespace) -> int:
    generated_at = _now_utc()
    _run_graph_builder()
    snapshots = _collect_snapshots()
    _write_memory_artifacts(snapshots, generated_at)
    print(f"Memory artifacts generated: modules={len(snapshots)}")

    if args.sync_repo_skill:
        copied = _sync_repo_skill_references()
        print(f"Repo skill references synced: files={copied}")
    if args.sync_local_skill:
        count = _sync_local_skill()
        print(f"Local CODEX skill synced: path={LOCAL_SKILL_DIR.as_posix()} entries={count}")
    ok, details = _health()
    if not ok:
        print(json.dumps(details, indent=2))
        return 1
    return 0


def cmd_health(_args: argparse.Namespace) -> int:
    ok, details = _health()
    print(json.dumps(details, indent=2))
    return 0 if ok else 1


def cmd_sync_repo_skill(_args: argparse.Namespace) -> int:
    copied = _sync_repo_skill_references()
    print(f"Repo skill references synced: files={copied}")
    return 0


def cmd_sync_local_skill(_args: argparse.Namespace) -> int:
    count = _sync_local_skill()
    print(f"Local CODEX skill synced: path={LOCAL_SKILL_DIR.as_posix()} entries={count}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python scripts/manage_acm_agent_memory.py",
        description="Manage Obsidian and skill-backed ACM agent memory.",
    )
    sub = ap.add_subparsers(dest="command", required=True)

    ap_refresh = sub.add_parser("refresh", help="Rebuild graph and memory artifacts")
    ap_refresh.add_argument("--sync-repo-skill", action="store_true", help="Sync generated references into repo skill folder")
    ap_refresh.add_argument("--sync-local-skill", action="store_true", help="Sync repo skill into local CODEX_HOME/skills")
    ap_refresh.set_defaults(func=cmd_refresh)

    ap_health = sub.add_parser("health", help="Run memory integrity checks")
    ap_health.set_defaults(func=cmd_health)

    ap_sync_repo = sub.add_parser("sync-repo-skill", help="Copy generated references into repo skill folder")
    ap_sync_repo.set_defaults(func=cmd_sync_repo_skill)

    ap_sync_local = sub.add_parser("sync-local-skill", help="Copy repo skill into local CODEX_HOME skill folder")
    ap_sync_local.set_defaults(func=cmd_sync_local_skill)

    return ap


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

