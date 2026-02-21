#!/usr/bin/env python3
"""
Build an Obsidian knowledge graph for the ACM codebase.

The script scans core/*.py and generates linked Markdown notes in:
docs/obsidian_vault/

Generated notes include:
- Module index
- Function and method index
- Per-module notes
- Per-function notes
- Runtime flow and output interpretation anchor notes

Usage:
    python scripts/build_acm_obsidian_graph.py
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = REPO_ROOT / "core"
VAULT_DIR = REPO_ROOT / "docs" / "obsidian_vault"
MODULES_DIR = VAULT_DIR / "modules"
FUNCTIONS_DIR = VAULT_DIR / "functions"


@dataclass
class FunctionInfo:
    full_name: str
    display_name: str
    module_name: str
    source_path: str
    line_start: int
    line_end: int
    doc_summary: str
    signature: str
    kind: str


@dataclass
class ModuleInfo:
    module_name: str
    source_path: str
    doc_summary: str
    core_imports: Set[str] = field(default_factory=set)
    functions: List[FunctionInfo] = field(default_factory=list)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _first_line(text: Optional[str]) -> str:
    if not text:
        return ""
    return text.strip().splitlines()[0].strip()


def _module_name_from_path(py_path: Path) -> str:
    rel = py_path.relative_to(REPO_ROOT).as_posix()
    if not rel.endswith(".py"):
        raise ValueError(f"Expected .py file, got: {rel}")
    return rel[:-3].replace("/", ".")


def _safe_node_end_lineno(node: ast.AST) -> int:
    end = getattr(node, "end_lineno", None)
    start = getattr(node, "lineno", None) or 1
    return int(end if end is not None else start)


def _render_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    try:
        args_str = ast.unparse(node.args)
    except Exception:
        args_str = "..."
    return f"{node.name}({args_str})"


def _resolve_import_from(
    current_module: str,
    node: ast.ImportFrom,
) -> Set[str]:
    """
    Resolve imported core modules from `from ... import ...` statements.
    """
    imports: Set[str] = set()
    level = int(getattr(node, "level", 0) or 0)
    module = node.module or ""

    if level == 0 and module.startswith("core"):
        imports.add(module)
        return imports

    if level > 0:
        current_parts = current_module.split(".")
        if level > len(current_parts):
            return imports
        base_parts = current_parts[: len(current_parts) - level]
        if module:
            base_parts = base_parts + module.split(".")

        for alias in node.names:
            if alias.name == "*":
                if base_parts:
                    imports.add(".".join(base_parts))
                continue
            candidate_parts = list(base_parts)
            if not module:
                candidate_parts.append(alias.name)
            candidate = ".".join(candidate_parts)
            if candidate.startswith("core."):
                imports.add(candidate)
            elif ".".join(base_parts).startswith("core."):
                imports.add(".".join(base_parts))

    return imports


def _collect_module_info(py_path: Path) -> ModuleInfo:
    source = py_path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(py_path))
    module_name = _module_name_from_path(py_path)
    module_summary = _first_line(ast.get_docstring(tree))
    info = ModuleInfo(
        module_name=module_name,
        source_path=py_path.relative_to(REPO_ROOT).as_posix(),
        doc_summary=module_summary,
    )

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("core."):
                    info.core_imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            info.core_imports.update(_resolve_import_from(module_name, node))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_name = f"{module_name}.{node.name}"
            func_info = FunctionInfo(
                full_name=func_name,
                display_name=node.name,
                module_name=module_name,
                source_path=info.source_path,
                line_start=int(node.lineno),
                line_end=_safe_node_end_lineno(node),
                doc_summary=_first_line(ast.get_docstring(node)),
                signature=_render_signature(node),
                kind="function",
            )
            info.functions.append(func_info)
        elif isinstance(node, ast.ClassDef):
            class_name = f"{module_name}.{node.name}"
            class_info = FunctionInfo(
                full_name=class_name,
                display_name=node.name,
                module_name=module_name,
                source_path=info.source_path,
                line_start=int(node.lineno),
                line_end=_safe_node_end_lineno(node),
                doc_summary=_first_line(ast.get_docstring(node)),
                signature=node.name,
                kind="class",
            )
            info.functions.append(class_info)
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_name = f"{module_name}.{node.name}.{child.name}"
                    method_info = FunctionInfo(
                        full_name=method_name,
                        display_name=f"{node.name}.{child.name}",
                        module_name=module_name,
                        source_path=info.source_path,
                        line_start=int(child.lineno),
                        line_end=_safe_node_end_lineno(child),
                        doc_summary=_first_line(ast.get_docstring(child)),
                        signature=_render_signature(child),
                        kind="method",
                    )
                    info.functions.append(method_info)

    info.core_imports.discard(module_name)
    return info


def _all_core_modules() -> List[Path]:
    files = sorted(CORE_DIR.glob("*.py"))
    return [p for p in files if p.name != "__init__.py"]


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def _cleanup_generated_notes() -> None:
    """
    Remove previously generated module/function notes.

    This prevents stale symbols from lingering in the vault when source code
    changes remove or rename functions.
    """
    for md in MODULES_DIR.glob("*.md"):
        md.unlink()
    for md in FUNCTIONS_DIR.glob("*.md"):
        md.unlink()


def _link_to_module(module_name: str) -> str:
    return f"[[modules/{module_name}|{module_name}]]"


def _link_to_function(full_name: str) -> str:
    return f"[[functions/{full_name}|{full_name}]]"


def _render_module_note(module: ModuleInfo, generated_at: str) -> str:
    imports = sorted(module.core_imports)
    function_links = sorted(module.functions, key=lambda f: (f.line_start, f.full_name))

    import_block = "\n".join(f"- {_link_to_module(m)}" for m in imports) or "- none"
    function_block = "\n".join(
        f"- {_link_to_function(f.full_name)} (line {f.line_start}, {f.kind})"
        for f in function_links
    ) or "- none"

    return f"""---
type: module
module: {module.module_name}
source: {module.source_path}
generated_at: {generated_at}
---

# {module.module_name}

Source file: `{module.source_path}`

Summary: {module.doc_summary or "no module docstring summary"}

## Imports from core
{import_block}

## Top-level symbols
{function_block}
"""


def _render_function_note(function: FunctionInfo, generated_at: str) -> str:
    return f"""---
type: {function.kind}
id: {function.full_name}
module: {function.module_name}
source: {function.source_path}
line_start: {function.line_start}
line_end: {function.line_end}
generated_at: {generated_at}
---

# {function.full_name}

Defined in: {_link_to_module(function.module_name)}

Source: `{function.source_path}:{function.line_start}`

Kind: `{function.kind}`

Signature: `{function.signature}`

Summary: {function.doc_summary or "no docstring summary"}
"""


def _render_home(modules: List[ModuleInfo], generated_at: str) -> str:
    module_count = len(modules)
    symbol_count = sum(len(m.functions) for m in modules)
    return f"""---
type: index
generated_at: {generated_at}
---

# ACM Obsidian Knowledge Graph

Generated from code in `core/`.

## Snapshot
- modules: {module_count}
- symbols (functions/classes/methods): {symbol_count}
- generated_at_utc: {generated_at}

## Start Here
- [[01_Modules]]
- [[02_Functions]]
- [[03_Runtime-Flow]]
- [[04_Outputs-and-Status]]
"""


def _render_module_index(modules: List[ModuleInfo], generated_at: str) -> str:
    lines = []
    for module in sorted(modules, key=lambda m: m.module_name):
        lines.append(
            f"- {_link_to_module(module.module_name)} "
            f"({module.source_path})"
        )
    listing = "\n".join(lines) or "- none"
    return f"""---
type: index
generated_at: {generated_at}
---

# Module Index

{listing}
"""


def _render_function_index(modules: List[ModuleInfo], generated_at: str) -> str:
    rows: List[str] = []
    for module in sorted(modules, key=lambda m: m.module_name):
        rows.append(f"## {module.module_name}")
        if not module.functions:
            rows.append("- none")
            continue
        for f in sorted(module.functions, key=lambda x: (x.kind, x.line_start, x.full_name)):
            rows.append(
                f"- {_link_to_function(f.full_name)} "
                f"(line {f.line_start}, {f.kind})"
            )
    content = "\n".join(rows)
    return f"""---
type: index
generated_at: {generated_at}
---

# Function and Symbol Index

{content}
"""


def _runtime_flow_note(generated_at: str) -> str:
    return f"""---
type: reference
generated_at: {generated_at}
---

# Runtime Flow

Primary runtime entrypoint is `python -m core.acm`.

Main high-level sequence:
1. parse args
2. initialize observability
3. connect SQL
4. load config and equipment context
5. start run and resolve window
6. load data and coldstart handling
7. data contract validation
8. feature build and imputation
9. load or fit models
10. score detectors
11. regime label and quality checks
12. calibrate and fuse
13. episode extraction
14. drift computation
15. persist outputs
16. write run metadata and finalize run

Read next:
- [[01_Modules]]
- [[04_Outputs-and-Status]]
"""


def _outputs_note(generated_at: str) -> str:
    return f"""---
type: reference
generated_at: {generated_at}
---

# Outputs and Status

Outcome semantics:
1. OK
2. DEGRADED
3. NOOP
4. FAIL

Primary output owner:
- [[modules/core.output_manager|core.output_manager]]

Primary run metadata owner:
- [[modules/core.run_metadata_writer|core.run_metadata_writer]]

Primary lifecycle table:
- ACM_Runs

High-value tables to inspect first:
1. ACM_Runs
2. ACM_Scores_Wide
3. ACM_Episodes
4. ACM_HealthTimeline
5. ACM_DriftController
6. ACM_DataQuality
"""


def _readme_note() -> str:
    return """# Obsidian Vault for ACM Codebase

This folder is an Obsidian-friendly knowledge graph generated from `core/*.py`.

## Regenerate

Run:

```powershell
python scripts/build_acm_obsidian_graph.py
```

## Open in Obsidian

1. Open this repository as an Obsidian vault.
2. Enable core plugin `Graph view`.
3. Open `docs/obsidian_vault/00_Home.md`.
4. Use graph view and backlinks to navigate module and function relationships.

## Recommended Obsidian Settings

1. Keep wikilinks enabled.
2. Keep automatic internal link updates enabled.
3. Enable local graph while editing deep notes.

## Notes

Generated notes are intended for navigation and context recall.
Do not manually edit generated module and function notes.
"""


def build_graph() -> Tuple[int, int]:
    generated_at = _utc_now_iso()
    module_infos = [_collect_module_info(p) for p in _all_core_modules()]
    all_symbols = sum(len(m.functions) for m in module_infos)

    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    MODULES_DIR.mkdir(parents=True, exist_ok=True)
    FUNCTIONS_DIR.mkdir(parents=True, exist_ok=True)
    _cleanup_generated_notes()

    _write(VAULT_DIR / "README.md", _readme_note())
    _write(VAULT_DIR / "00_Home.md", _render_home(module_infos, generated_at))
    _write(VAULT_DIR / "01_Modules.md", _render_module_index(module_infos, generated_at))
    _write(VAULT_DIR / "02_Functions.md", _render_function_index(module_infos, generated_at))
    _write(VAULT_DIR / "03_Runtime-Flow.md", _runtime_flow_note(generated_at))
    _write(VAULT_DIR / "04_Outputs-and-Status.md", _outputs_note(generated_at))

    for module in module_infos:
        _write(MODULES_DIR / f"{module.module_name}.md", _render_module_note(module, generated_at))
        for symbol in module.functions:
            _write(FUNCTIONS_DIR / f"{symbol.full_name}.md", _render_function_note(symbol, generated_at))

    return len(module_infos), all_symbols


def main() -> None:
    module_count, symbol_count = build_graph()
    print(f"Generated Obsidian graph notes: modules={module_count}, symbols={symbol_count}")
    print(f"Output directory: {VAULT_DIR.as_posix()}")


if __name__ == "__main__":
    main()
