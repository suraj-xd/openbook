# Openbook Agent Instructions

You are working inside the `openbook` repo. Your job is to help the user get lawful book files into `books/` with as little friction as possible.

## Primary User Flow

When the user gives only a book name, treat it as a request to find and download a lawful copy. Do not ask routine setup or workflow questions. Proceed with the default flow below.

Default flow:

1. Search for public-domain, open-license, or otherwise authorized editions of the requested book.
2. Prefer sources clearly marked as Project Gutenberg, Standard Ebooks, Wikisource, OpenStax, government/public-domain, Creative Commons, or an official publisher/open-access source.
3. If using Anna's Archive, use it only to retrieve a lawful public-domain/open-license/authorized file.
4. Use the `annas-to-notebooklm` skill's Anna's Archive download behavior, but skip every NotebookLM action.
5. Save the downloaded file into `books/`.
6. Update `books/index.md` with the title, filename, source URL, format, and date.
7. Report the saved path and anything that failed.

Ask a question only when the title is ambiguous enough that choosing automatically would likely fetch the wrong book, or when the user asks for a commercial/copyrighted title without a lawful access path.

## Important Boundaries

This repo is against piracy. Do not help download unauthorized copyrighted books.

If the requested title appears to be commercially copyrighted and no lawful public-domain/open-license/authorized source is visible, do not download it. Instead, provide legal access options such as publisher pages, libraries, Open Library controlled lending, Google Books previews, or purchase links.

Do not upload anything to NotebookLM. Do not create a notebook. Do not call the original skill's upload-to-NotebookLM path.

Do not convert EPUB/PDF files. Do not base64 encode files. Do not delete the final file unless the user explicitly asks. Keep the successful download in `books/`.

## Expected Repo Layout

- `books/` is the only destination for downloaded book files.
- `books/index.md` is the local catalog.
- `.openbook/annas-to-notebooklm/` may contain a cloned copy of the source skill.
- `scripts/find_public_domain_candidates.py` helps find public-domain-like Anna's Archive candidates.
- `scripts/download_with_skill.py` clones the original skill for reference, runs only the Anna's Archive browser-download flow, and saves into `books/`.

## Setup Commands

Run these if the environment is not ready:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

If the agent supports Codex/Claude skills, this is optional:

```bash
npx skills add https://github.com/zstmfhy/annas-to-notebooklm --skill annas-to-notebooklm
```

The local helper can clone the source skill automatically, so do not block on the skill install if `git` is available.

## Anna's Archive Flow

For a public-domain/open-license/authorized title:

1. Search Anna's Archive using the title plus a public-domain source hint, for example `Project Gutenberg` or `Standard Ebooks`.
2. Select a matching `/md5/...` result only after checking the metadata text.
3. Run the browser flow from the MD5 page; do not treat raw `curl` mirror probing as the decision point.
4. Open the MD5 page and find slow download links.
5. Prefer `/0/4` when it exists, otherwise use the first discovered slow-download URL.
6. Use visible/headful Playwright because DDoS-Guard can appear on slow-download pages.
7. Wait through browser-check text for up to 120 seconds.
8. Extract the direct URL from `span.bg-gray-200`.
9. Trigger the browser download.
10. Save the resulting file into `books/`.

The helper accepts an MD5 page, raw MD5 hash, or selected slow-download URL:

```bash
python scripts/download_with_skill.py "https://annas-archive.gl/md5/fb73d4fd19b0da98923365cb85a03a2b"
python scripts/download_with_skill.py "fb73d4fd19b0da98923365cb85a03a2b"
python scripts/download_with_skill.py "https://annas-archive.gl/slow_download/fb73d4fd19b0da98923365cb85a03a2b/0/4"
```

If running in a Linux sandbox without a visible display, use `xvfb-run -a` and do not manually force `DISPLAY=:99`:

```bash
xvfb-run -a .venv/bin/python scripts/download_with_skill.py "<md5_or_slow_url>"
```

For E2B-style sandboxes that require `/home/user/files`, use:

```bash
OPENBOOK_BOOKS_DIR=/home/user/files xvfb-run -a .venv/bin/python scripts/download_with_skill.py "<md5_or_slow_url>"
```

This repo defaults to `books/`; `/home/user/files` is only for sandboxes that explicitly require it.

## Browser Check Rules

The browser flow must wait until these browser-check markers disappear:

- `ddos-guard`
- `checking your browser`
- `please wait`
- `cloudflare`
- `just a moment`
- `verify you are human`

Do not check content immediately after navigation and declare failure. The slow-download page can show browser-check text for several seconds before proceeding.

If the browser itself still receives an Envoy/TLS upstream error after waiting, report that as a live browser-flow failure. Do not use a separate `curl` failure as proof that the browser flow cannot work.

## Candidate Search

Use:

```bash
python scripts/find_public_domain_candidates.py "<book title and author>"
```

Treat its results as candidates, not final proof. Prefer records whose visible metadata clearly says Project Gutenberg, Standard Ebooks, Wikisource, OpenStax, public domain, or Creative Commons.

## File Handling

After a successful download:

1. Confirm the file exists under `books/`.
2. Confirm size is nonzero.
3. Keep the file in `books/`.
4. Update `books/index.md`.
5. Do not move book files outside `books/`.
6. Report the selected slow-download URL, whether `span.bg-gray-200` was found, direct URL prefix, final filename, absolute path, byte size, and format.

## Failure Reporting

If something breaks, report the exact failing stage:

- search page
- md5 page
- DDoS-Guard
- slow-download page
- direct-link extraction
- file download
