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

## Expected Repo Layout

- `books/` is the only destination for downloaded book files.
- `books/index.md` is the local catalog.
- `.openbook/annas-to-notebooklm/` may contain a cloned copy of the source skill.
- `scripts/find_public_domain_candidates.py` helps find public-domain-like Anna's Archive candidates.
- `scripts/download_with_skill.py` imports the original skill downloader and saves into `books/`.

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
3. Open the MD5 page and find slow download links.
4. Prefer a no-waitlist slow partner link when visible.
5. Use visible/headful Playwright because DDoS-Guard can appear on slow-download pages.
6. Wait until the final page loads.
7. Extract the direct URL from `span.bg-gray-200`.
8. Trigger the browser download.
9. Save the resulting file into `books/`.

The source skill's downloader already implements steps 5-9 for a slow-download URL. Use:

```bash
python scripts/download_with_skill.py "<slow_download_url>"
```

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

## Failure Reporting

If something breaks, report the exact failing stage:

- environment setup
- candidate search
- MD5 page selection
- DDoS-Guard/browser check
- slow-download page
- `span.bg-gray-200` direct-link extraction
- browser download
- save into `books/`

