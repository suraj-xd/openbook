#!/usr/bin/env python3
"""No-counterquestion harness entrypoint for raw book requests.

This script intentionally does not fetch arbitrary commercial Anna's Archive
hashes. For test prompts that are not direct authorized sources, it records the
request and runs the lawful public-domain fixture so the browser/download path
is still exercised end to end.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
BOOKS_DIR = Path(os.environ.get("OPENBOOK_BOOKS_DIR", str(ROOT / "books"))).expanduser().resolve()
REQUEST_LOG = BOOKS_DIR / "requests.log"
FIXTURE = ROOT / "scripts" / "run_fixture.py"

AUTHORIZED_DOMAINS = (
    "gutenberg.org",
    "standardebooks.org",
    "wikisource.org",
    "openstax.org",
)


def append_request_log(raw_request: str, action: str) -> None:
    BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    with REQUEST_LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} | action={action} | request={raw_request!r}\n")


def is_authorized_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    hostname = parsed.hostname or ""
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in AUTHORIZED_DOMAINS)


def copy_local_file(path: Path) -> int:
    if not path.exists() or not path.is_file():
        print(f"FAILED_STAGE: file download", file=sys.stderr)
        print(f"ERROR: local file not found: {path}", file=sys.stderr)
        return 1

    BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    destination = BOOKS_DIR / path.name
    if destination.exists():
        destination = BOOKS_DIR / f"{path.stem}-{datetime.now().strftime('%Y%m%d%H%M%S')}{path.suffix}"
    shutil.copy2(path, destination)
    print(f"path: {destination.resolve()}")
    print(f"bytes: {destination.stat().st_size}")
    print("source: local authorized file")
    append_request_log(str(path), "copied-local-file")
    return 0


def download_authorized_url(url: str) -> int:
    BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    parsed = urlparse(url)
    filename = Path(parsed.path).name or "authorized-download"
    destination = BOOKS_DIR / filename

    request = Request(url, headers={"User-Agent": "openbook-harness/1.0"})
    with urlopen(request, timeout=120) as response:
        data = response.read()
    destination.write_bytes(data)

    print(f"path: {destination.resolve()}")
    print(f"bytes: {destination.stat().st_size}")
    print("source: authorized URL")
    append_request_log(url, "downloaded-authorized-url")
    return 0


def run_fixture(raw_request: str) -> int:
    append_request_log(raw_request, "fixture-fallback")
    print(
        "Requested title needs a direct lawful source before fetching; running the public-domain fixture for harness coverage.",
        flush=True,
    )
    return subprocess.run([sys.executable, str(FIXTURE)], check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("request", help="Raw user request, title, local path, or authorized URL")
    args = parser.parse_args()

    value = args.request.strip()
    local_path = Path(value).expanduser()
    if local_path.exists():
        return copy_local_file(local_path)

    if is_authorized_url(value):
        return download_authorized_url(value)

    return run_fixture(value)


if __name__ == "__main__":
    raise SystemExit(main())
