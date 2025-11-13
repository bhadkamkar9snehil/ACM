# utils/logger.py
from __future__ import annotations
import json, sys, time
from pathlib import Path
from typing import Callable, Dict, Any

class Console:
    """Tiny console logger with the interface acm_main expects."""
    @staticmethod
    def info(msg: str) -> None:  print(msg, file=sys.stdout)
    @staticmethod
    def ok(msg: str)   -> None:  print(msg, file=sys.stdout)
    @staticmethod
    def warn(msg: str) -> None:  print(msg, file=sys.stdout)
    @staticmethod
    def error(msg: str)-> None:  print(msg, file=sys.stderr)

    # Add a compatibility shim for 'warning' to alias 'warn'.
    warning = warn

def jsonl_logger(path: Path) -> Callable[[Dict[str, Any]], None]:
    """
    Append JSON lines to `path` with a simple writer:
      {"event":"START","block":"FEATURES","t":...}
      {"event":"END","block":"FEATURES","t":...,"dt_s":...}
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = path.open("a", encoding="utf-8")
    def write(obj: Dict[str, Any]) -> None:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
        fh.flush()
    return write
