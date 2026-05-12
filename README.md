# openbook

Openbook is a small Claude-ready workspace for finding lawful book files and saving them into `books/`.

The repo is designed for public-domain, open-license, or otherwise authorized books. It is against piracy. Do not use this project to obtain unauthorized copies of copyrighted books.

## How It Works

Open this repo with Claude and ask for a book by name:

```text
Pride and Prejudice by Jane Austen
```

Claude should read `CLAUDE.md`, search for a lawful candidate, use the Anna's Archive automation flow from `annas-to-notebooklm`, skip NotebookLM entirely, and save the downloaded file into `books/`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

Optional, if your agent supports skills:

```bash
npx skills add https://github.com/zstmfhy/annas-to-notebooklm --skill annas-to-notebooklm
```

The helper script can also clone the source skill into `.openbook/annas-to-notebooklm` automatically.

## Useful Commands

Find likely public-domain candidates:

```bash
python scripts/find_public_domain_candidates.py "Pride and Prejudice Jane Austen"
```

Download from an already selected Anna's Archive slow-download URL:

```bash
python scripts/download_with_skill.py "https://annas-archive.gl/slow_download/fb73d4fd19b0da98923365cb85a03a2b/0/4"
```

Downloaded files are written to `books/`. The script also appends a simple entry to `books/index.md`.

## Notes

Use visible/headful Chromium for Anna's Archive. Some slow-download pages can show a browser check before the final page appears.

