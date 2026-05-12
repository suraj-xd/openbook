#!/usr/bin/env python3
"""Run the default public-domain browser-download fixture."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_MD5 = "fb73d4fd19b0da98923365cb85a03a2b"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the default public-domain browser-download fixture.")
    parser.parse_args()

    command = [
        sys.executable,
        str(ROOT / "scripts" / "download_with_skill.py"),
        FIXTURE_MD5,
    ]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
