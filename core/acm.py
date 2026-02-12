# core/acm.py
"""
ACM v11.8 Entry Point

Single entry point that runs the adaptive ACM pipeline.

Usage:
    python -m core.acm --equip FD_FAN
    python -m core.acm --equip FD_FAN --start-time 2024-01-01T00:00:00
    python -m core.acm --equip FD_FAN --force-retrain

The system automatically decides whether to train or score based on
model state and quality metrics. No manual mode selection needed.
"""
import argparse
import sys


def main() -> int:
    """Main entry point for ACM."""
    ap = argparse.ArgumentParser(
        prog="python -m core.acm",
        description="ACM v11.8 - Automated Condition Monitoring (Adaptive)",
        epilog="""
The pipeline automatically determines behavior:
  - No models cached: trains fresh models (coldstart)
  - Models cached + quality OK: scores with cached models
  - Models cached + quality degraded: retrains automatically

Examples:
  python -m core.acm --equip FD_FAN
  python -m core.acm --equip FD_FAN --start-time 2023-01-01T00:00:00
  python -m core.acm --equip FD_FAN --force-retrain
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--equip", required=True, help="Equipment name (e.g., FD_FAN)")
    ap.add_argument("--start-time", help="Start time (ISO format)")
    ap.add_argument("--end-time", help="End time (ISO format)")
    ap.add_argument("--force-retrain", action="store_true",
                    help="Force model retraining regardless of quality")
    ap.add_argument("--clear-cache", action="store_true",
                    help="Clear cached models before running")
    ap.add_argument("--config", help="Config file path")
    ap.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO")

    args = ap.parse_args()

    # Build command args for acm_main
    cmd_args = ["--equip", args.equip]
    if args.start_time:
        cmd_args.extend(["--start-time", args.start_time])
    if args.end_time:
        cmd_args.extend(["--end-time", args.end_time])
    if args.force_retrain:
        cmd_args.append("--force-retrain")
    if args.clear_cache:
        cmd_args.append("--clear-cache")
    if args.config:
        cmd_args.extend(["--config", args.config])
    if args.log_level:
        cmd_args.extend(["--log-level", args.log_level])

    sys.argv = ["acm_main"] + cmd_args

    try:
        from core import acm_main
        acm_main.main()
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    except Exception as e:
        print(f"[ACM] Pipeline failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
