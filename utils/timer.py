# utils/timer.py
from __future__ import annotations
import atexit, time, os, functools
from typing import Any, Callable, Dict

class Timer:
    """Lightweight stage timer. Usage:
       T = Timer();  with T.section("load_data"): ...;  T.log("custom", extra="info")
    """
    def __init__(self, enable: bool | None = None):
        self.enable = bool(int(os.getenv("ACM_TIMINGS", "1"))) if enable is None else enable
        self.sections: Dict[str, float] = {}
        self.totals: Dict[str, float] = {}
        self._stack: list[str] = []
        self._t0 = time.perf_counter()
        atexit.register(self._print_summary)

    def section(self, name: str):
        if not self.enable:
            return _NullContext()
        self.sections[name] = time.perf_counter()
        self._stack.append(name)
        return _Close(self, name)

    def end(self, name: str):
        if not self.enable: 
            return 0.0
        t1 = time.perf_counter()
        t0 = self.sections.pop(name, t1)
        dur = t1 - t0
        self.totals[name] = self.totals.get(name, 0.0) + dur
        print(f"[TIMER] {name:<20} {dur:7.3f}s")
        return dur

    def wrap(self, name: str):
        """Decorator: @T.wrap('features') on a function."""
        def deco(fn: Callable[..., Any]):
            @functools.wraps(fn)
            def inner(*a, **k):
                with self.section(name):
                    return fn(*a, **k)
            return inner
        return deco

    def log(self, name: str, **kv: Any):
        if not self.enable: 
            return
        extra = " ".join(f"{k}={v}" for k, v in kv.items())
        print(f"[TIMER] {name:<20} {extra}".rstrip())

    def _print_summary(self):
        if not self.enable: 
            return
        total = time.perf_counter() - self._t0
        if self.totals:
            print("[TIMER] -- Summary ------------------------------")
            for k, v in sorted(self.totals.items(), key=lambda x: -x[1]):
                pct = (v / total) * 100.0 if total > 0 else 0.0
                print(f"[TIMER] {k:<20} {v:7.3f}s ({pct:5.1f}%)")
        print(f"[TIMER] total_run            {total:7.3f}s")

class _Close:
    def __init__(self, T: Timer, name: str): self.T, self.name = T, name
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): self.T.end(self.name)

class _NullContext:
    def __enter__(self): return self
    def __exit__(self, *a): return False
