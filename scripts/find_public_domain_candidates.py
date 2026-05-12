#!/usr/bin/env python3
"""Find likely lawful/public-domain Anna's Archive candidates for a title."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from html import unescape
from urllib.parse import quote_plus, urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


BASE_URL = "https://annas-archive.gl"
PUBLIC_HINTS = (
    "Project Gutenberg",
    "Standard Ebooks",
    "Wikisource",
    "OpenStax",
    "public domain",
    "Creative Commons",
    "CC BY",
)


@dataclass(frozen=True)
class Candidate:
    title: str
    url: str
    snippet: str


def fetch(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
            )
        },
    )
    with urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def looks_lawful(text: str) -> bool:
    lowered = text.lower()
    return any(hint.lower() in lowered for hint in PUBLIC_HINTS)


def compact(text: str, limit: int = 260) -> str:
    text = " ".join(unescape(text).split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def extract_candidates(html: str) -> list[Candidate]:
    soup = BeautifulSoup(html, "lxml")
    seen: set[str] = set()
    candidates: list[Candidate] = []

    for link in soup.select('a.js-vim-focus[href^="/md5/"]'):
        href = link.get("href", "")
        if href in seen:
            continue
        seen.add(href)

        block = link.find_parent("div", class_=lambda value: value and "border-b" in value)
        text = block.get_text(" ", strip=True) if block else link.get_text(" ", strip=True)
        if not looks_lawful(text):
            continue

        candidates.append(
            Candidate(
                title=compact(link.get_text(" ", strip=True), 120),
                url=urljoin(BASE_URL, href),
                snippet=compact(text),
            )
        )

    return candidates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="Book title and optional author")
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()

    searches = [
        args.query,
        f"{args.query} Project Gutenberg",
        f"{args.query} Standard Ebooks",
        f"{args.query} Wikisource",
    ]

    combined: dict[str, Candidate] = {}
    for query in searches:
        search_url = f"{BASE_URL}/search?q={quote_plus(query)}"
        try:
            for candidate in extract_candidates(fetch(search_url)):
                combined.setdefault(candidate.url, candidate)
        except Exception as exc:  # noqa: BLE001
            print(f"search failed for {query!r}: {exc}", file=sys.stderr)

    if not combined:
        print("No public-domain/open-license candidates found.")
        return 1

    for index, candidate in enumerate(list(combined.values())[: args.limit], start=1):
        print(f"{index}. {candidate.title}")
        print(f"   {candidate.url}")
        print(f"   {candidate.snippet}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

