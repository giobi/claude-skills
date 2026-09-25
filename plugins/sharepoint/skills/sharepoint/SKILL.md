---
name: sharepoint
description: "SharePoint access via Microsoft Graph — browse sites, search, read and upload files. Reuses the email skill's O365 token."
user-invocable: true
argument-hint: "[cherche <query>|sites|lis <fichier>|upload <fichier>]"
---

# `/sharepoint` — SharePoint via Microsoft Graph

Read and write files on the company SharePoint. Same OAuth token as the email skill (`O365_*` in `.env`) — no separate login, no extra consent.

## NLP-first

Interpret natural language, don't demand rigid syntax:

- "cherche le fichier X sur SharePoint" → `search_all(X)` first — tenant-wide, no guessing
- "montre-moi les sites SharePoint" → list sites
- "lis le doc Y dans Recruitment" → `search_all` → download → read content
- "mets ce rapport sur SharePoint dans Z" → upload with confirmation of destination
- "lis le fichier Excel X, quelles colonnes il a?" → `read_xlsx` on the located drive/path

## Usage

```bash
python3 .claude/skills/sharepoint/sharepoint.py search-all "<query>"     # search EVERYWHERE, start here
python3 .claude/skills/sharepoint/sharepoint.py sites [query]
python3 .claude/skills/sharepoint/sharepoint.py drives <site-id>
python3 .claude/skills/sharepoint/sharepoint.py ls <drive-id> [path]
python3 .claude/skills/sharepoint/sharepoint.py search <drive-id> "<query>"
python3 .claude/skills/sharepoint/sharepoint.py get <drive-id> "<path>" [local_dest]
python3 .claude/skills/sharepoint/sharepoint.py put <drive-id> <local_file> "<remote_path>"
python3 .claude/skills/sharepoint/sharepoint.py read_xlsx <drive-id> "<path>" [sheet] [max_rows]
```

Or from Python:

```python
import sys; sys.path.insert(0, '.claude/skills/sharepoint')
from sharepoint import sites, drives, ls, search, search_all, get, put, read_xlsx
```

## Workflow: find a file when the user names it loosely

**Start with `search_all(query)` — it searches every SharePoint site and drive you
can access in one call.** No need to guess a site name first: guessing wrong (e.g.
trying "Recruitment", "Recruitment Team", "GR Team" by hand) can silently miss a
file sitting in a different site, and reporting "no file found" from a partial
guess is worse than not searching at all. `search_all()` returns `site_id` and
`drive_id` for each hit, which is everything the rest of the steps below need.

1. `search_all(query)` — tenant-wide, returns matching files with their site/drive ids
2. `get(drive_id, path)` — downloads into `storage/sharepoint/` (use the `webUrl`/path from the hit)
3. Read/convert locally (pdf, docx, xlsx) and answer — for `.xlsx` use `read_xlsx` (see below)

Only fall back to the manual `sites()` → `drives()` → `search(drive_id, ...)` path
when `search_all()` comes back empty and you want to browse a specific site by eye,
or when you already know exactly which drive to search and want to skip the
tenant-wide call.

Cache useful site/drive ids in `wiki/skills/sharepoint.md` as you discover them, so future lookups skip the browsing steps.

## Excel files — `read_xlsx`

For `.xlsx`/`.xlsm` files, don't `get()` + guess the format by hand: use
`read_xlsx(drive_id, path, sheet=None, max_rows=200)`. It downloads to
`storage/tmp/` (a working copy, not the persisted `storage/sharepoint/`) and
returns `{sheet, headers, rows, total_rows, truncated}` — the first row is
taken as headers, `rows` holds up to `max_rows` data rows, `total_rows` is the
real row count, and `truncated` tells you whether you're seeing the whole
sheet or just the head of it.

If `truncated` is `True`, **say so explicitly** before summarizing — the brain
is a notebook, not an archive: don't claim to have read a file you only saw
the first 200 rows of. Pick a specific `sheet` by name when the workbook has
more than one and the user named it, otherwise the active sheet is used.

If this raises "openpyxl not installed", it's not a skill bug: the brain
container image is missing the library. That's a `codefix` in `abchat-infra`
(`docker/Dockerfile.brain`), not something the skill or a live `pip install`
can fix — a runtime `pip install` is lost the moment the container restarts.

## Pattern — "fammi dieci domande" before mapping a file into the wiki

Before writing anything from a SharePoint file (Excel, Word, PDF) into
`wiki/`, don't summarize-and-commit on the first read. Read the file, then ask
about ten concrete questions back — one per column/section that isn't
self-evident: what each column means, which rows are stale/test data, what
the cadence is (daily? per-deal?), who else edits it, what should NOT end up
in the wiki (PII, draft numbers). A wiki card built from a guessed reading of
someone else's working spreadsheet is worse than no card — it's confidently
wrong. This is the same discipline as the fishbowl-context rule of "verify at
the source, don't deduce it": the columns and their meaning are on the sheet
in front of you, but what a column is *for* usually isn't — that's the part
worth ten questions instead of one confident guess.

## Rules

- **Downloads land in `storage/sharepoint/`** (or `storage/tmp/` for `read_xlsx`'s working copy) — never in wiki/ or public/.
- **Uploads and overwrites: confirm destination with the user first.** Reading is free, writing is announced.
- Files >4MB: upload not supported in v1 — say so instead of failing silently.
- Token refresh is shared with the email skill: if email works, SharePoint works. If both fail with 401 after refresh, the refresh token expired → re-run the email skill's oauth-reauthorize flow.
- **`search_all()` only returns `driveItem` hits Graph considers indexed and permission-visible to this token** — an empty result means "not found or not indexed", not a hard guarantee the file doesn't exist. If a file is expected but missing, say so explicitly rather than reporting a flat "no such file".

## Config

Optional `wiki/skills/sharepoint.md` frontmatter:

```yaml
default_site: <site-id>      # site to assume when user doesn't specify
known_drives:
  recruitment: <drive-id>
  gr-team: <drive-id>
```

## v1 limits (evolve later)

- Simple upload only (<4MB), no upload sessions
- No sharing-link creation, no permissions management
- No delta sync / change tracking

## Changelog

- **1.3 (2026-09-25)** — merged `search_all()` into the shared skill. It had been added
  on 2026-09-18 to a single brain's local copy, forked from 1.1, which also dropped
  `read_xlsx` and the symlink-aware O365 driver lookup. 1.3 is 1.2 plus `search_all`,
  so no feature is traded for another. Every brain now points at the shared copy.
- **1.2 (2026-09-16)** — `read_xlsx()`, symlink-aware O365 driver resolution.
- `search_all()` root cause: on 2026-09-18 the site-guessing path reported "no file
  found" for Grohe/Lixil/alumni records that existed and were found instantly once
  searched tenant-wide. → village TODO #1598
