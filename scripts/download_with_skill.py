#!/usr/bin/env python3
"""Run only the Anna's Archive browser-download flow and save into books/.

The repo behind the original skill is cloned for reference, but this script
intentionally does not invoke any NotebookLM, upload, or conversion path.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BOOKS_DIR = ROOT / "books"
DEFAULT_SKILL_DIR = ROOT / ".openbook" / "annas-to-notebooklm"
SKILL_REPO = "https://github.com/zstmfhy/annas-to-notebooklm.git"
DEFAULT_BASE_URL = "https://annas-archive.gl"

CHECK_TEXTS = (
    "ddos-guard",
    "checking your browser",
    "please wait",
    "cloudflare",
    "just a moment",
    "verify you are human",
)


class DownloadFlowError(RuntimeError):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage


@dataclass(frozen=True)
class FlowResult:
    selected_slow_url: str
    span_found: bool
    direct_url_prefix: str
    filename: str
    path: Path
    size: int
    file_format: str


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def ensure_skill_repo(skill_dir: Path) -> None:
    """Keep the source skill available locally without running its upload flow."""

    upload_py = skill_dir / "scripts" / "upload.py"
    if upload_py.exists():
        return

    skill_dir.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", "--depth=1", SKILL_REPO, str(skill_dir)])

    test_download = skill_dir / "scripts" / "test_download.py"
    if not upload_py.exists() or not test_download.exists():
        raise FileNotFoundError(
            "Source skill clone is missing scripts/upload.py or scripts/test_download.py"
        )


def normalize_annas_url(value: str, base_url: str) -> str:
    value = value.strip()
    if re.fullmatch(r"[a-fA-F0-9]{32}", value):
        return f"{base_url}/md5/{value.lower()}"
    if value.startswith("/"):
        return urljoin(base_url, value)
    return value


def extract_md5(value: str) -> str | None:
    match = re.search(r"/(?:md5|slow_download)/([a-fA-F0-9]{32})(?:/|$)", value)
    if match:
        return match.group(1).lower()
    if re.fullmatch(r"[a-fA-F0-9]{32}", value):
        return value.lower()
    return None


def is_slow_download_url(url: str) -> bool:
    return "/slow_download/" in url


async def page_text(page) -> str:
    try:
        return await page.locator("body").inner_text(timeout=5_000)
    except PlaywrightError:
        return ""


async def wait_through_browser_check(page, stage: str, timeout_seconds: int) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    elapsed = 0

    while True:
        title = (await page.title()).lower()
        body = (await page_text(page)).lower()
        if not any(text in title or text in body for text in CHECK_TEXTS):
            if elapsed:
                print(f"{stage}: browser check cleared after {elapsed}s", flush=True)
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise DownloadFlowError(stage, "browser check did not finish")
        if elapsed % 10 == 0:
            print(f"{stage}: browser check still present at {elapsed}s", flush=True)
        await asyncio.sleep(5)
        elapsed += 5


async def goto_and_wait(page, url: str, stage: str, timeout_seconds: int) -> None:
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=90_000)
    except PlaywrightTimeoutError as exc:
        raise DownloadFlowError(stage, f"navigation timed out: {exc}") from exc

    await wait_through_browser_check(page, stage, timeout_seconds)


async def choose_slow_url(page, md5_url: str, preferred_index: int, base_url: str) -> str:
    md5 = extract_md5(md5_url)
    links = await page.eval_on_selector_all(
        "a[href]",
        "els => els.map(a => a.href || a.getAttribute('href')).filter(Boolean)",
    )
    if not md5:
        slow_links = [href for href in links if "/slow_download/" in href]
    else:
        slow_links = [href for href in links if f"/slow_download/{md5}" in href]

    if not slow_links:
        raise DownloadFlowError("md5 page", "no slow-download links found")

    absolute_links = [urljoin(base_url, href) for href in slow_links]
    preferred_suffix = f"/0/{preferred_index}"
    for href in absolute_links:
        if urlparse(href).path.endswith(preferred_suffix):
            return href
    return absolute_links[0]


async def extract_direct_url(page) -> tuple[str, bool]:
    try:
        await page.wait_for_selector("span.bg-gray-200", timeout=15_000)
    except PlaywrightTimeoutError as exc:
        raise DownloadFlowError("slow-download page", "direct-link span was not found") from exc

    spans = await page.query_selector_all("span.bg-gray-200")
    for span in spans:
        text = (await span.inner_text()).strip()
        if text.startswith(("http://", "https://")):
            return text, True

    raise DownloadFlowError(
        "direct-link extraction",
        "span.bg-gray-200 existed, but no span text started with http",
    )


def safe_download_path(directory: Path, filename: str) -> Path:
    name = filename.replace("/", "_").replace("\0", "").strip() or "book-download"
    candidate = directory / name
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    for index in range(2, 1000):
        next_candidate = directory / f"{stem}-{index}{suffix}"
        if not next_candidate.exists():
            return next_candidate

    raise DownloadFlowError("file download", f"could not choose a unique path for {name}")


def detect_format(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    return suffix or "unknown"


def append_catalog(
    books_dir: Path,
    result: FlowResult,
    source_url: str,
) -> None:
    index_path = books_dir / "index.md"
    if not index_path.exists():
        index_path.write_text("# Openbook Catalog\n\n", encoding="utf-8")

    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    entry = (
        f"- {timestamp} | `{result.filename}` | {result.file_format} | "
        f"bytes: {result.size} | source: {source_url} | slow: {result.selected_slow_url}\n"
    )
    with index_path.open("a", encoding="utf-8") as handle:
        handle.write(entry)


async def run_flow(args: argparse.Namespace) -> FlowResult:
    base_url = args.base_url.rstrip("/")
    source_url = normalize_annas_url(args.url, base_url)
    books_dir = Path(args.books_dir).expanduser().resolve()
    books_dir.mkdir(parents=True, exist_ok=True)

    ensure_skill_repo(Path(args.skill_dir).expanduser().resolve())

    async with async_playwright() as playwright:
        print(f"launching_chromium_headless: {args.headless}", flush=True)
        browser = await playwright.chromium.launch(
            headless=args.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-download-notification",
                "--disable-infobars",
            ],
        )
        context = await browser.new_context(
            accept_downloads=True,
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1365, "height": 900},
        )
        page = await context.new_page()
        page.set_default_timeout(90_000)

        try:
            if is_slow_download_url(source_url):
                selected_slow_url = source_url
            else:
                print(f"opening_md5_page: {source_url}", flush=True)
                await goto_and_wait(
                    page,
                    source_url,
                    "md5 page",
                    args.browser_check_timeout,
                )
                selected_slow_url = await choose_slow_url(
                    page,
                    source_url,
                    args.preferred_slow_index,
                    base_url,
                )
                print(f"selected_slow_url: {selected_slow_url}", flush=True)

            print(f"opening_slow_download_page: {selected_slow_url}", flush=True)
            await goto_and_wait(
                page,
                selected_slow_url,
                "DDoS-Guard",
                args.browser_check_timeout,
            )
            await asyncio.sleep(args.settle_seconds)

            direct_url, span_found = await extract_direct_url(page)
            print("span_bg_gray_200_found: True", flush=True)
            print(f"direct_url_prefix: {direct_url[:120]}", flush=True)

            print("starting_browser_download: True", flush=True)
            async with page.expect_download(timeout=args.download_timeout * 1000) as download_info:
                try:
                    await page.goto(direct_url, wait_until="commit", timeout=90_000)
                except PlaywrightError:
                    # Chromium often raises while transitioning into a download.
                    pass

            download = await download_info.value
            destination = safe_download_path(books_dir, download.suggested_filename)
            print(f"saving_download_as: {destination}", flush=True)
            await download.save_as(destination)
        finally:
            await context.close()
            await browser.close()

    destination = destination.resolve()
    if destination.parent != books_dir:
        raise DownloadFlowError("file download", f"file saved outside books dir: {destination}")

    size = destination.stat().st_size if destination.exists() else 0
    if size <= 0:
        raise DownloadFlowError("file download", "downloaded file is missing or empty")

    return FlowResult(
        selected_slow_url=selected_slow_url,
        span_found=span_found,
        direct_url_prefix=direct_url[:120],
        filename=destination.name,
        path=destination,
        size=size,
        file_format=detect_format(destination),
    )


async def download(args: argparse.Namespace) -> int:
    try:
        result = await run_flow(args)
    except DownloadFlowError as exc:
        print(f"FAILED_STAGE: {exc.stage}", file=sys.stderr)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    append_catalog(Path(args.books_dir).expanduser().resolve(), result, args.url)
    print(f"selected_slow_url: {result.selected_slow_url}")
    print(f"span_bg_gray_200_found: {result.span_found}")
    print(f"direct_url_prefix: {result.direct_url_prefix}")
    print(f"filename: {result.filename}")
    print(f"path: {result.path}")
    print(f"bytes: {result.size}")
    print(f"format: {result.file_format}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "url",
        help="Anna's Archive MD5 page, slow-download URL, or raw 32-char MD5 hash",
    )
    parser.add_argument("--books-dir", default=os.environ.get("OPENBOOK_BOOKS_DIR", str(DEFAULT_BOOKS_DIR)))
    parser.add_argument("--skill-dir", default=str(DEFAULT_SKILL_DIR))
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--preferred-slow-index", type=int, default=4)
    parser.add_argument("--browser-check-timeout", type=int, default=120)
    parser.add_argument("--download-timeout", type=int, default=180)
    parser.add_argument("--settle-seconds", type=float, default=3)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    return asyncio.run(download(args))


if __name__ == "__main__":
    raise SystemExit(main())
