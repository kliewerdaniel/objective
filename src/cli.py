#!/usr/bin/env python3
"""CLI launcher for objective03."""

import sys
import argparse
from pathlib import Path


def cmd_run(args):
    from src.main import main
    import asyncio
    asyncio.run(main(headless=not args.dashboard))


def cmd_download(args):
    from src.models.download import main as dl_main
    sys.argv = ["objective03-download"] + args.args
    dl_main()


def cmd_check(args):
    """Verify system dependencies and configuration."""
    checks = []
    # Check Python
    checks.append(("Python >= 3.11", sys.version_info >= (3, 11)))

    # Check pip packages
    try:
        import kuzu
        checks.append(("kuzu", True))
    except ImportError:
        checks.append(("kuzu", False))
    try:
        import llama_cpp
        checks.append(("llama-cpp-python", True))
    except ImportError:
        checks.append(("llama-cpp-python", False))
    try:
        import textual
        checks.append(("textual", True))
    except ImportError:
        checks.append(("textual", False))

    # Check external tools
    import shutil
    checks.append(("piper (brew)", shutil.which("piper") is not None))
    checks.append(("ffmpeg", shutil.which("ffmpeg") is not None))

    # Check config
    from src.config import DATA_DIR
    config_path = DATA_DIR / "config.yaml"
    checks.append(("config.yaml", config_path.exists()))

    # Check models
    models_dir = DATA_DIR / "models"
    ggufs = list(models_dir.glob("*.gguf")) if models_dir.exists() else []
    checks.append(("GGUF models", len(ggufs) > 0, f"{len(ggufs)} found"))

    print("objective03 system check:")
    all_pass = True
    for check in checks:
        name = check[0]
        status = check[1]
        detail = check[2] if len(check) > 2 else ""
        symbol = "OK" if status else "FAIL"
        print(f"  [{symbol}] {name} {detail}")
        if not status:
            all_pass = False

    if all_pass:
        print("\nAll checks passed.")
    else:
        print("\nSome checks failed. See above.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="objective03 — synthetic epistemology engine")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    run_parser = subparsers.add_parser("run", help="Start the daemon")
    run_parser.add_argument("--dashboard", action="store_true", help="Show terminal UI dashboard")
    run_parser.set_defaults(func=cmd_run)

    dl_parser = subparsers.add_parser("download", help="Download models")
    dl_parser.add_argument("args", nargs=argparse.REMAINDER)
    dl_parser.set_defaults(func=cmd_download)

    check_parser = subparsers.add_parser("check", help="Check system dependencies")
    check_parser.set_defaults(func=cmd_check)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
