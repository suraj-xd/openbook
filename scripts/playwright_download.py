#!/usr/bin/env python3
"""
Standalone Playwright downloader for Anna's Archive.

Decision point is the browser flow, NOT curl/mirror probing.
Run under xvfb-run so headless=False works in a headless environment:

    xvfb-run -a python scripts/playwright_download.py <md5_or_slow_url>

The script:
  1. Navigates the MD5 page (or accepts a slow-download URL directly).
  2. Waits through any browser-check page (DDoS-Guard, Cloudflare, etc.).
  3. Finds slow-download links, preferring the /0/4 partner slot.
  4. On the slow-download page waits again through browser-check, then
     extracts the direct URL from span.bg-gray-200.
  5. Triggers a browser download of that URL.
  6. Saves the file into books/ (or --dest).
  7. Appends an entry to books/index.md.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEST = ROOT / "books"
INDEX_FILE = DEFAULT_DEST / "index.md"

BASE = "https://annas-archive.gl"

# Texts that indicate a browser-check interstitial is still showing.
CHECK_TEXTS = [
    "ddos-guard",
    "checking your browser",
    "please wait",
    "cloudflare",
    "just a moment",
    "verify you are human",
]

# Preferred slow-download partner slot order.
PREFERRED_SLOTS = ["/0/4", "/0/3", "/0/2", "/0/1", "/0/0", "/0/5"]

BROWSER_CHECK_TIMEOUT = 120  # seconds to wait for browser-check to clear
DOWNLOAD_TIMEOUT = 180_000   # ms for the actual file download


def md5_from_arg(value: str) -> str:
    """Return the 32-char MD5 hex string from a URL or bare hash."""
    m = re.search(r"/md5/([0-9a-f]{32})", value)
    if m:
        return m.group(1)
    m = re.search(r"/slow_download/([0-9a-f]{32})", value)
    if m:
        return m.group(1)
    if re.fullmatch(r"[0-9a-f]{32}", value):
        return value
    raise ValueError(f"Cannot extract MD5 from: {value!r}")


async def wait_through_check(page, label: str, timeout: int = BROWSER_CHECK_TIMEOUT) -> None:
    """Poll until none of the browser-check strings appear in page content."""
    for elapsed in range(timeout):
        content = (await page.content()).lower()
        if not any(t in content for t in CHECK_TEXTS):
            return
        if elapsed % 10 == 0:
            print(f"  [{label}] browser-check present at {elapsed}s, waiting…")
        await asyncio.sleep(1)
    # Final check — raise if still showing.
    content = (await page.content()).lower()
    if any(t in content for t in CHECK_TEXTS):
        raise TimeoutError(f"[{label}] browser-check did not clear after {timeout}s")


async def get_slow_links(page, md5: str) -> list[str]:
    """Return slow-download hrefs from the MD5 page, preferred slots first."""
    all_hrefs: list[str] = await page.eval_on_selector_all(
        "a[href]",
        "els => els.map(a => a.href || a.getAttribute('href')).filter(Boolean)",
    )
    slow = [h for h in all_hrefs if f"/slow_download/{md5}" in h]
    # Sort by preferred slot order; unknown slots go last.
    def slot_rank(href: str) -> int:
        for i, slot in enumerate(PREFERRED_SLOTS):
            if href.endswith(slot):
                return i
        return len(PREFERRED_SLOTS)
    slow.sort(key=slot_rank)
    return slow


async def extract_direct_url(page) -> str | None:
    """Pull the direct download URL out of span.bg-gray-200 elements."""
    spans = await page.query_selector_all("span.bg-gray-200")
    for span in spans:
        txt = (await span.inner_text()).strip()
        if txt.startswith("http://") or txt.startswith("https://"):
            return txt
    return None


async def run(md5: str, dest: Path, source_hint: str) -> int:
    dest.mkdir(parents=True, exist_ok=True)
    md5_url = f"{BASE}/md5/{md5}"

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        context = await browser.new_context(
            accept_downloads=True,
            ignore_https_errors=True,
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1365, "height": 900},
        )
        page = await context.new_page()

        # ── Step 1: MD5 page ────────────────────────────────────────────────
        print(f"Opening MD5 page: {md5_url}")
        await page.goto(md5_url, wait_until="domcontentloaded", timeout=90_000)
        await wait_through_check(page, "md5-page")
        print("  MD5 page loaded.")

        # ── Step 2: Find slow-download links ────────────────────────────────
        slow_links = await get_slow_links(page, md5)
        if not slow_links:
            print("ERROR: no slow-download links found on MD5 page.", file=sys.stderr)
            await browser.close()
            return 1
        print(f"  Found {len(slow_links)} slow-download link(s).")
        for link in slow_links:
            print(f"    {link}")

        slow_url = slow_links[0]
        print(f"\nOpening slow-download page: {slow_url}")

        # ── Step 3: Slow-download page ──────────────────────────────────────
        await page.goto(slow_url, wait_until="domcontentloaded", timeout=90_000)
        await wait_through_check(page, "slow-page")
        print("  Slow-download page loaded.")

        # ── Step 4: Extract direct URL ──────────────────────────────────────
        direct_url = await extract_direct_url(page)
        if not direct_url:
            print("ERROR: span.bg-gray-200 direct URL not found.", file=sys.stderr)
            print("  Page content snippet:")
            content = await page.content()
            print(content[:2000])
            await browser.close()
            return 1
        print(f"  Direct URL: {direct_url}")

        # ── Step 5: Trigger browser download ────────────────────────────────
        print("\nStarting download…")
        async with page.expect_download(timeout=DOWNLOAD_TIMEOUT) as dl_info:
            try:
                await page.goto(direct_url, wait_until="commit", timeout=90_000)
            except Exception:
                # "Download is starting" navigation abort is expected.
                pass

        download = await dl_info.value
        suggested = download.suggested_filename or f"{md5}.bin"
        dest_path = dest / suggested
        await download.save_as(str(dest_path))
        await browser.close()

        # ── Step 6: Validate ─────────────────────────────────────────────────
        if not dest_path.exists() or dest_path.stat().st_size == 0:
            print(f"ERROR: download file missing or empty: {dest_path}", file=sys.stderr)
            return 1

        size = dest_path.stat().st_size
        print(f"\nSaved: {dest_path}")
        print(f"Bytes: {size:,}")

        # ── Step 7: Update index ─────────────────────────────────────────────
        _append_index(dest_path, source_hint or slow_url, dest)
        return 0


def _append_index(file_path: Path, source_url: str, books_dir: Path) -> None:
    index = books_dir / "index.md"
    if not index.exists():
        index.write_text("# Openbook Catalog\n\nDownloaded lawful book files are listed here.\n", encoding="utf-8")
    suffix = file_path.suffix.lstrip(".").upper() or "unknown"
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d")
    entry = f"| {timestamp} | `{file_path.name}` | {suffix} | {source_url} |\n"
    # Write header row if not present
    text = index.read_text(encoding="utf-8")
    if "| Date |" not in text:
        with index.open("a", encoding="utf-8") as fh:
            fh.write("\n| Date | File | Format | Source |\n")
            fh.write("|------|------|--------|--------|\n")
    with index.open("a", encoding="utf-8") as fh:
        fh.write(entry)
    print(f"Index updated: {index}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download from Anna's Archive via Playwright (no curl gating)."
    )
    parser.add_argument(
        "target",
        help="MD5 hash, /md5/... URL, or /slow_download/... URL",
    )
    parser.add_argument(
        "--dest",
        default=str(DEFAULT_DEST),
        help="Destination directory (default: books/)",
    )
    parser.add_argument(
        "--source-hint",
        default="",
        help="Human-readable source label for index.md",
    )
    args = parser.parse_args()

    md5 = md5_from_arg(args.target)
    dest = Path(args.dest).expanduser().resolve()
    return asyncio.run(run(md5, dest, args.source_hint))


if __name__ == "__main__":
    raise SystemExit(main())
