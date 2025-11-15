"""Utility to replay chunked data through ACM sequentially or in parallel.

Usage examples:
    python chunk_replay.py --equip FD_FAN GAS_TURBINE
    python chunk_replay.py --max-workers 2 --dry-run

The first chunk for each asset is used for cold-start bootstrapping
(train + score). Subsequent chunks are scored only, allowing the cached
models to evolve hands-off just like production historian ingestion.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import textwrap
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import re
from typing import Iterable, List, Dict, Set

# Add project root to path for imports
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from utils.logger import Console


def _discover_assets(chunk_root: Path, requested: Iterable[str] | None) -> List[str]:
    if requested:
        return [asset for asset in requested if (chunk_root / asset).exists()]
    return sorted(p.name for p in chunk_root.iterdir() if p.is_dir())


def _get_progress_file(artifact_root: Path) -> Path:
    """Get path to the progress tracking file."""
    return artifact_root / ".chunk_replay_progress.json"


def _load_progress(artifact_root: Path) -> Dict[str, Set[str]]:
    """Load progress tracking state from JSON file.
    
    Returns:
        Dictionary mapping asset name to set of completed chunk filenames
    """
    progress_file = _get_progress_file(artifact_root)
    if not progress_file.exists():
        return {}
    
    try:
        with open(progress_file, "r") as f:
            data = json.load(f)
            # Convert lists back to sets
            return {asset: set(chunks) for asset, chunks in data.items()}
    except (json.JSONDecodeError, OSError) as exc:
        Console.warn(f"[WARN] Could not load progress file: {exc}", error=str(exc))
        return {}


def _save_progress(artifact_root: Path, progress: Dict[str, Set[str]]) -> None:
    """Save progress tracking state to JSON file."""
    progress_file = _get_progress_file(artifact_root)
    
    try:
        # Convert sets to lists for JSON serialization
        data = {asset: sorted(chunks) for asset, chunks in progress.items()}
        with open(progress_file, "w") as f:
            json.dump(data, f, indent=2)
    except OSError as exc:
        Console.warn(f"[WARN] Could not save progress file: {exc}", error=str(exc))


def _mark_chunk_completed(artifact_root: Path, asset: str, chunk_name: str) -> None:
    """Mark a chunk as completed for an asset."""
    progress = _load_progress(artifact_root)
    if asset not in progress:
        progress[asset] = set()
    progress[asset].add(chunk_name)
    _save_progress(artifact_root, progress)


def _chunk_sort_key(path: Path) -> tuple[int, str]:
    match = re.search(r"(\d+)", path.stem)
    index = int(match.group(1)) if match else 0
    return index, path.name


def _load_chunks(chunk_dir: Path) -> List[Path]:
    if not chunk_dir.exists():
        return []
    files = [p for p in chunk_dir.iterdir() if p.is_file() and p.suffix.lower() == ".csv"]
    return sorted(files, key=_chunk_sort_key)


def _build_command(equip: str, artifact_root: Path, chunk_path: Path, *, bootstrap: bool,
                   clear_cache: bool, acm_args: List[str]) -> List[str]:
    # Create equipment-specific artifact path
    equip_artifact_root = artifact_root / equip
    cmd = [sys.executable, "-m", "core.acm_main", "--equip", equip,
           "--artifact-root", str(equip_artifact_root), "--score-csv", str(chunk_path)]
    if bootstrap:
        cmd.extend(["--train-csv", str(chunk_path)])
        if clear_cache:
            cmd.append("--clear-cache")
    if acm_args:
        cmd.extend(acm_args)
    return cmd


def _run_chunk_command(cmd: List[str], *, dry_run: bool) -> int:
    printable = " ".join(cmd)
    if dry_run:
        Console.info(f"[DRY] {printable}", mode="dry-run")
        return 0
    Console.info(f"[RUN] {printable}", command=printable)
    result = subprocess.run(cmd, check=False)
    return result.returncode


def _process_asset(equip: str, chunk_root: Path, artifact_root: Path, *, dry_run: bool,
                   clear_cache: bool, acm_args: List[str], resume: bool) -> None:
    chunk_dir = chunk_root / equip
    chunks = _load_chunks(chunk_dir)
    if not chunks:
        raise RuntimeError(f"No chunks found for {equip} under {chunk_dir}")

    # Load progress tracking if resuming
    completed_chunks: Set[str] = set()
    if resume:
        progress = _load_progress(artifact_root)
        completed_chunks = progress.get(equip, set())
        if completed_chunks:
            Console.info(f"[INFO] {equip}: resuming from previous run ({len(completed_chunks)} chunks already completed)", equipment=equip, completed=len(completed_chunks))

    total = len(chunks)
    remaining = [c for c in chunks if c.name not in completed_chunks]
    
    if not remaining:
        Console.info(f"[INFO] {equip}: all {total} chunks already completed, skipping", equipment=equip, total=total)
        return
    
    Console.info(f"[INFO] {equip}: processing {len(remaining)}/{total} chunk(s) from {chunk_dir}", equipment=equip, remaining=len(remaining), total=total)

    for idx, chunk_path in enumerate(chunks, start=1):
        # Skip already completed chunks
        if chunk_path.name in completed_chunks:
            Console.info(f"[INFO] {equip}: chunk {idx}/{total} (skipped) -> {chunk_path.name}", equipment=equip, chunk=idx, total=total)
            continue
            
        bootstrap = idx == 1
        phase = "bootstrap" if bootstrap else "score"
        Console.info(f"[INFO] {equip}: chunk {idx}/{total} ({phase}) -> {chunk_path.name}", equipment=equip, chunk=idx, total=total, phase=phase)
        cmd = _build_command(
            equip,
            artifact_root,
            chunk_path,
            bootstrap=bootstrap,
            clear_cache=clear_cache and bootstrap,
            acm_args=acm_args,
        )
        code = _run_chunk_command(cmd, dry_run=dry_run)
        if code != 0:
            raise RuntimeError(
                f"ACM run failed for {equip} chunk {chunk_path.name} (exit code {code})"
            )
        
        # Mark chunk as completed
        if not dry_run:
            _mark_chunk_completed(artifact_root, equip, chunk_path.name)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay chunked historian slices through ACM hands-off runs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Notes:
              • Chunk directory defaults to data/chunked/<EQUIP>/batch_*.csv.
              • First chunk per asset is used for cold-start training and scoring.
              • Later chunks reuse cached models and only score new data.
              • Use --acm-args -- --enable-report to forward custom flags to ACM.
              • Use --resume to skip already-completed chunks (progress tracked in .chunk_replay_progress.json).
        """),
    )
    parser.add_argument("--equip", nargs="*", help="Specific equipment codes to replay")
    parser.add_argument("--chunk-root", default="data/chunked", help="Path to chunked data root")
    parser.add_argument("--artifact-root", default="artifacts", help="ACM artifact root directory")
    parser.add_argument("--max-workers", type=int, default=1,
                        help="Number of assets to process in parallel")
    parser.add_argument("--clear-cache", action="store_true",
                        help="Pass --clear-cache on the bootstrap chunk")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from last successful chunk (skip completed chunks)")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without running")
    parser.add_argument("--acm-args", nargs=argparse.REMAINDER, default=[],
                        help="Additional arguments appended to each ACM invocation")

    args = parser.parse_args()

    chunk_root = Path(args.chunk_root).resolve()
    artifact_root = Path(args.artifact_root).resolve()

    if args.acm_args and args.acm_args[0] == "--":
        args.acm_args = args.acm_args[1:]

    assets = _discover_assets(chunk_root, args.equip)
    if not assets:
        Console.error(f"[ERROR] No assets found under {chunk_root}", chunk_root=str(chunk_root))
        return 1

    max_workers = max(1, args.max_workers)
    errors: List[str] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(
                _process_asset,
                equip,
                chunk_root,
                artifact_root,
                dry_run=args.dry_run,
                clear_cache=args.clear_cache,
                acm_args=args.acm_args,
                resume=args.resume,
            ): equip for equip in assets
        }
        for future in as_completed(future_map):
            equip = future_map[future]
            try:
                future.result()
            except Exception as exc:  # noqa: BLE001 - want full context
                errors.append(f"{equip}: {exc}")
                Console.error(f"[ERROR] {equip}: {exc}", equipment=equip, error=str(exc))

    if errors:
        Console.error("[ERROR] One or more chunk replays failed:")
        for line in errors:
            Console.error(f"  - {line}")
        return 1

    Console.ok("[OK] Chunk replay complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
