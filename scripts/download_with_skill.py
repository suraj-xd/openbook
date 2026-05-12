#!/usr/bin/env python3
"""Download a selected Anna's Archive slow-download URL into books/ using the source skill."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BOOKS_DIR = ROOT / "books"
DEFAULT_SKILL_DIR = ROOT / ".openbook" / "annas-to-notebooklm"
SKILL_REPO = "https://github.com/zstmfhy/annas-to-notebooklm.git"


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def ensure_skill(skill_dir: Path) -> Path:
    upload_py = skill_dir / "scripts" / "upload.py"
    if upload_py.exists():
        return upload_py

    skill_dir.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", "--depth=1", SKILL_REPO, str(skill_dir)])

    if not upload_py.exists():
        raise FileNotFoundError(f"Could not find skill downloader at {upload_py}")
    return upload_py


def load_uploader(upload_py: Path):
    spec = importlib.util.spec_from_file_location("annas_to_notebooklm_upload", upload_py)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {upload_py}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.AnnasArchiveAutoUploader


def append_catalog(books_dir: Path, downloaded_file: Path, source_url: str, file_format: str | None) -> None:
    index_path = books_dir / "index.md"
    if not index_path.exists():
        index_path.write_text("# Openbook Catalog\n\n", encoding="utf-8")

    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    entry = (
        f"- {timestamp} | `{downloaded_file.name}` | "
        f"{file_format or 'unknown'} | source: {source_url}\n"
    )
    with index_path.open("a", encoding="utf-8") as handle:
        handle.write(entry)


async def download(args: argparse.Namespace) -> int:
    books_dir = Path(args.books_dir).expanduser().resolve()
    books_dir.mkdir(parents=True, exist_ok=True)

    upload_py = ensure_skill(Path(args.skill_dir).expanduser().resolve())
    uploader_class = load_uploader(upload_py)

    uploader = uploader_class()
    uploader.downloads_dir = books_dir

    downloaded_file, file_format = await uploader.download_from_annas(args.url)
    if not downloaded_file or not Path(downloaded_file).exists():
        print("Download failed: no file was saved.", file=sys.stderr)
        return 1

    downloaded_file = Path(downloaded_file).resolve()
    if downloaded_file.parent != books_dir:
        print(f"Download saved outside books dir: {downloaded_file}", file=sys.stderr)
        return 1

    size = downloaded_file.stat().st_size
    if size <= 0:
        print(f"Download saved an empty file: {downloaded_file}", file=sys.stderr)
        return 1

    append_catalog(books_dir, downloaded_file, args.url, file_format)
    print(f"Saved: {downloaded_file}")
    print(f"Format: {file_format or 'unknown'}")
    print(f"Bytes: {size}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="Anna's Archive slow-download URL")
    parser.add_argument("--books-dir", default=str(DEFAULT_BOOKS_DIR))
    parser.add_argument("--skill-dir", default=str(DEFAULT_SKILL_DIR))
    args = parser.parse_args()

    return asyncio.run(download(args))


if __name__ == "__main__":
    raise SystemExit(main())

