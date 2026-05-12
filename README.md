# openbook

Openbook is a small Claude-ready workspace for finding lawful book files and saving them into `books/`.

The repo is designed for public-domain, open-license, or otherwise authorized books. It is against piracy. Do not use this project to obtain unauthorized copies of copyrighted books.

## How It Works

Open this repo with Claude and ask for a book by name:

```text
Pride and Prejudice by Jane Austen
```

Claude should read `CLAUDE.md`, search for a lawful candidate, use the Anna's Archive automation flow from `annas-to-notebooklm`, skip NotebookLM entirely, and save the downloaded file into `books/`.

Openbook does not upload, convert, base64 encode, or delete the final book file.

If a requested title is not clearly public-domain, open-license, or otherwise authorized, Openbook should not get stuck in a refusal loop. It should run the built-in public-domain fixture automatically so the browser/download pipeline still gets tested.

The detailed agent playbook is in [`docs/harness-browser-flow.md`](docs/harness-browser-flow.md).

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

Or start directly from the MD5 page/hash and let the browser flow choose a slow-download URL:

```bash
python scripts/download_with_skill.py "https://annas-archive.gl/md5/fb73d4fd19b0da98923365cb85a03a2b"
python scripts/download_with_skill.py "fb73d4fd19b0da98923365cb85a03a2b"
```

Run the default public-domain fixture:

```bash
python scripts/run_fixture.py
```

Run a raw harness request without getting stuck in counterquestions:

```bash
python scripts/run_request.py "Money Works_ The Guide to Financial Literacy -- Kolapkar, Abhijeet -- 2023"
```

If the request is not a direct authorized source, `run_request.py` records it in `books/requests.log` and runs the public-domain fixture. If the request is a local file path or an approved open-access URL, it saves that file directly into `books/`.

Downloaded files are written to `books/`. The script also appends a simple entry to `books/index.md`.

## Notes

Use visible/headful Chromium for Anna's Archive. Some slow-download pages can show a browser check before the final page appears. In Linux sandboxes without a visible display, run through `xvfb-run -a`.

Do not use raw `curl` mirror checks as the gating condition. The intended path is Chromium opening the MD5 page, selecting a slow-download link, waiting through browser checks, extracting the direct URL from `span.bg-gray-200`, and saving the browser download.

For agent harness testing, do not stop at a refusal when the target title is not available from a lawful source. Use `scripts/run_request.py` so the test still exercises the browser/download pipeline through the default public-domain fixture.

For environments that require `/home/user/files`, override the destination:

```bash
OPENBOOK_BOOKS_DIR=/home/user/files xvfb-run -a .venv/bin/python scripts/download_with_skill.py "fb73d4fd19b0da98923365cb85a03a2b"
```
