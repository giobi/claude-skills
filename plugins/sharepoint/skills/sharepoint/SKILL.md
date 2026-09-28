---
name: sharepoint
description: "SharePoint access via Microsoft Graph. `find` locates anything tenant-wide in one call; then read, download or upload. Reuses the email skill's O365 token."
user-invocable: true
argument-hint: "[find <query>|read <file>|upload <file>|browse]"
---

# `/sharepoint` — SharePoint via Microsoft Graph

Read and write files on the company SharePoint. Same OAuth token as the email skill (`O365_*` in `.env`) — no separate login, no extra consent.

## The only rule that matters

**To locate anything, call `find`. Always. There is no second option.**

```bash
python3 .claude/skills/sharepoint/sharepoint.py find "<query>"
```

`find` searches the whole tenant in one call — every team site, every document
library, every personal OneDrive this token can see. It does not ask which site
to look in, because the site is exactly what nobody knows up front.

Call it even when the request names a place ("the contract in Recruitment"): the
named site is regularly not where the file sits. On 2026-09-28 a brain picked
three plausible sites for "Herta" and answered **1 file**. `find("Herta")`
returned **25** on the same token, including the client folder, the fee
spreadsheet and the signed 2026 contract — all in a drive the site walk never
opened.

## What `find` gives back

```json
{
  "query": "Herta",
  "results": [
    {"name": "Herta", "kind": "folder",
     "path": "Desktop/Missions Recruitment/Herta",
     "drive_name": "OneDrive", "drive_id": "b!…", "site_id": "…", "item_id": "01ZAU…",
     "size": 0, "modified": "2026-02-05T15:45:10Z",
     "matched_on": "name", "snippet": "", "webUrl": "https://…"}
  ],
  "coverage": {"method": "…", "scope": "…", "returned": 25, "duplicates_removed": 0,
               "more_available": true, "sites_with_hits": 2, "drives_with_hits": 2,
               "limits": ["…"]}
}
```

- **`results` is ordered**: exact name matches, then name prefixes, then names
  containing the query, then files that only matched on their *content*
  (`matched_on: "content"` — the query is inside the document, not in its name).
  Newest first inside each group. Duplicates are already removed.
- **Every record is self-sufficient.** `path` + `drive_id` feed `get`, `read_xlsx`
  and `ls` directly; `item_id` feeds `get_item`. No second lookup round.
- **`coverage` is not decoration — read it before answering.** It says what was
  searched and what the search cannot promise. Specifically:
  - `returned` is the real count. **`index_total_reported` is not** — it is the
    relevance engine's own inflated number (432 for a query with 25 real hits).
  - `more_available: true` or `truncated_at_limit: true` → there is more behind
    `limit`. Say so, or re-run with a higher limit.
  - An empty `results` means **"not found or not indexed"**, never "does not
    exist". Report it that way.

## Workflow: from a question to an answer

1. `find(query)` — locate it. Report `coverage` honestly if the answer is thin.
2. `get(drive_id, path)` (or `get_item(drive_id, item_id)` when `path` is empty)
   — downloads into `storage/sharepoint/`.
3. Read/convert locally and answer. For `.xlsx` skip step 2 and use `read_xlsx`.

## NLP-first

Interpret natural language, don't demand rigid syntax:

- "cherche le fichier X sur SharePoint" → `find(X)`
- "lis le doc Y dans Recruitment" → `find(Y)` → `get` → read. The site name in the
  request is a hint about the answer, not an instruction about where to search.
- "lis le fichier Excel X, quelles colonnes il a?" → `find(X)` → `read_xlsx`
- "mets ce rapport sur SharePoint dans Z" → `find(Z)` to locate the target folder,
  then upload with confirmation of the destination
- "montre-moi les sites SharePoint" → `browse()` — this is the one request that is
  genuinely about sites rather than about a file

## The exceptions

Everything below is an escape hatch, for when you deliberately want to look
inside one known place. None of them is the way to locate a file.

```bash
python3 .claude/skills/sharepoint/sharepoint.py browse [site]        # sites, then one site's drives
python3 .claude/skills/sharepoint/sharepoint.py get <drive-id> "<path>" [local_dest]
python3 .claude/skills/sharepoint/sharepoint.py get-item <drive-id> <item-id> [local_dest]
python3 .claude/skills/sharepoint/sharepoint.py read_xlsx <drive-id> "<path>" [sheet] [max_rows]
python3 .claude/skills/sharepoint/sharepoint.py put <drive-id> <local_file> "<remote_path>"
python3 .claude/skills/sharepoint/sharepoint.py ls <drive-id> [path]
python3 .claude/skills/sharepoint/sharepoint.py sites [query]
python3 .claude/skills/sharepoint/sharepoint.py drives <site-id>
python3 .claude/skills/sharepoint/sharepoint.py search <drive-id> "<query>"
python3 .claude/skills/sharepoint/sharepoint.py search-all "<query>"   # flat find(), pre-1.4 callers
```

`browse`, `sites`, `drives` and `search` print a line naming `find` before they
answer, on stderr. **That line is not noise — it is there because these verbs miss
personal OneDrive entirely**: `sites()` cannot enumerate it, so a walk built on it
will report "not found" for files that exist. If you reached one of these verbs
while looking for a file, you took a wrong turn; go back to `find`.

From Python:

```python
import sys; sys.path.insert(0, '.claude/skills/sharepoint')
from sharepoint import find, browse, get, get_item, read_xlsx, put
from sharepoint import sites, drives, ls, search, search_all   # escape hatches
```

Cache useful site/drive ids in `wiki/skills/sharepoint.md` as you discover them — handy for repeated writes to the same folder, never a substitute for `find`.

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
- **`find()` only returns `driveItem` hits Graph considers indexed and permission-visible to this token** — an empty result means "not found or not indexed", not a hard guarantee the file doesn't exist. If a file is expected but missing, say so explicitly rather than reporting a flat "no such file". The `coverage.limits` list in every result spells this out; quote it rather than paraphrasing.

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

- **1.4 (2026-09-28)** — `find()` becomes the single entry point, and `browse()` the
  named exploratory verb. Nothing was removed: `sites`, `drives`, `ls`, `search`,
  `get`, `put`, `read_xlsx` and `search_all` keep their signatures, and `search_all`
  is now a thin flat-list wrapper over `find`. New: `get_item()` (download by the id
  `find` returns).
  Root cause this fixes: 1.3 already said "start with `search_all` — tenant-wide, no
  guessing", and a brain still did the site walk for "Herta" and answered 1 file
  instead of 25. The instruction was correct and was skipped, so **another
  instruction was not the fix** — the fix is that the obvious verb now does the
  right thing without anyone choosing it. `find` always searches tenant-wide,
  dedupes, ranks name matches above content matches, resolves each hit's
  drive-relative path from the drive's own webUrl, and returns a `coverage` block so
  a thin answer stays diagnosable instead of passing as silent truth. The verbs that
  walk sites by hand now announce `find` on stderr before answering.
- **1.3 (2026-09-25)** — merged `search_all()` into the shared skill. It had been added
  on 2026-09-18 to a single brain's local copy, forked from 1.1, which also dropped
  `read_xlsx` and the symlink-aware O365 driver lookup. 1.3 is 1.2 plus `search_all`,
  so no feature is traded for another. Every brain now points at the shared copy.
- **1.2 (2026-09-16)** — `read_xlsx()`, symlink-aware O365 driver resolution.
- `search_all()` root cause: on 2026-09-18 the site-guessing path reported "no file
  found" for Grohe/Lixil/alumni records that existed and were found instantly once
  searched tenant-wide. → village TODO #1598
