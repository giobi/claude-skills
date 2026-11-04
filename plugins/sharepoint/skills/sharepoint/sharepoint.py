#!/usr/bin/env python3
"""
SharePoint wrapper via Microsoft Graph.

Reuses the O365 OAuth token from the email skill (same .env, same refresh flow).
The app registration already carries Sites.ReadWrite.All + Files.ReadWrite.All.

CLI — `find` is the entry point. Everything under it is an exception:

    sharepoint.py find <query> [limit]       # THE way to locate anything. Whole tenant, one call.

    sharepoint.py browse [site]              # exploratory walk (sites, then drives). Guessing path.
    sharepoint.py get <drive-id> <path> [local_dest]          # download a file
    sharepoint.py get-item <drive-id> <item-id> [local_dest]  # download by item id (from find)
    sharepoint.py read_xlsx <drive-id> <path> [sheet] [max_rows]  # headers + rows of an Excel file
    sharepoint.py put <drive-id> <local_file> <path>          # upload a file (<4MB)
    sharepoint.py ls <drive-id> [path]       # list folder content
    sharepoint.py sites [query]              # raw site list (browse() is the friendlier form)
    sharepoint.py drives <site-id>           # document libraries of a site
    sharepoint.py search <drive-id> <query>  # search inside ONE drive you already know
    sharepoint.py search-all <query>         # flat list from find(); kept for existing callers

Python:
    import sys; sys.path.insert(0, '.claude/skills/sharepoint')
    from sharepoint import find, browse, get, get_item, read_xlsx, put
    from sharepoint import sites, drives, ls, search, search_all  # granular escape hatches
"""

import json
import sys
from pathlib import Path
from urllib.parse import unquote

import requests

# Reuse token machinery from the email skill's o365 driver — single token store.
# Do NOT resolve() symlinks first: in shared installs .claude/skills/sharepoint
# points at shared/skills/sharepoint/<ver>/ and the sibling is then
# shared/skills/email/current/drivers/o365, not shared/skills/email/drivers/o365.
_O365_CANDIDATES = [
    Path(__file__).absolute().parents[1] / 'email' / 'drivers' / 'o365',
    Path(__file__).resolve().parents[2] / 'email' / 'current' / 'drivers' / 'o365',
    Path(__file__).resolve().parents[1] / 'email' / 'drivers' / 'o365',
]
_O365_DRIVER = next((c for c in _O365_CANDIDATES if (c / 'o365.py').exists()), _O365_CANDIDATES[0])
sys.path.insert(0, str(_O365_DRIVER))
from o365 import _get_env, _refresh_access_token, find_env_file  # noqa: E402

GRAPH = 'https://graph.microsoft.com/v1.0'


def _request(method: str, url: str, retry: bool = True, **kwargs):
    """Graph call with cached access token; on 401 refresh once and retry."""
    env_file = find_env_file()
    token = _get_env('O365_ACCESS_TOKEN', env_file)
    if not token:
        token = _refresh_access_token(env_file)
    headers = kwargs.pop('headers', {})
    headers['Authorization'] = f'Bearer {token}'
    resp = requests.request(method, url, headers=headers, **kwargs)
    if resp.status_code == 401 and retry:
        token = _refresh_access_token(env_file)
        headers['Authorization'] = f'Bearer {token}'
        resp = requests.request(method, url, headers=headers, **kwargs)
    if resp.status_code >= 400:
        raise RuntimeError(f'Graph {method} {url} -> {resp.status_code}: {resp.text[:500]}')
    return resp


def _get_json(url: str, **kwargs) -> dict:
    return _request('GET', url, **kwargs).json()


def _paged(url: str, limit: int = 200) -> list:
    """Follow @odata.nextLink up to `limit` items."""
    items = []
    while url and len(items) < limit:
        data = _get_json(url)
        items.extend(data.get('value', []))
        url = data.get('@odata.nextLink')
    return items[:limit]


def sites(query: str = '*') -> list:
    """List/search SharePoint sites. Returns [{id, name, webUrl}]."""
    data = _paged(f'{GRAPH}/sites?search={requests.utils.quote(query or "*")}'
                  f'&$select=id,displayName,webUrl')
    return [{'id': s['id'], 'name': s.get('displayName', ''), 'webUrl': s.get('webUrl', '')}
            for s in data]


def drives(site_id: str) -> list:
    """Document libraries of a site. Returns [{id, name, webUrl}]."""
    data = _paged(f'{GRAPH}/sites/{site_id}/drives?$select=id,name,webUrl,driveType')
    return [{'id': d['id'], 'name': d.get('name', ''), 'webUrl': d.get('webUrl', ''),
             'type': d.get('driveType', '')} for d in data]


def _item_url(drive_id: str, path: str) -> str:
    path = (path or '').strip('/')
    return f'{GRAPH}/drives/{drive_id}/root' + (f':/{requests.utils.quote(path)}:' if path else '')


def ls(drive_id: str, path: str = '') -> list:
    """List a folder. Returns [{name, folder, size, modified, id, webUrl}]."""
    url = _item_url(drive_id, path) + '/children?$select=id,name,size,folder,lastModifiedDateTime,webUrl&$top=200'
    return [{'name': i['name'],
             'folder': 'folder' in i,
             'size': i.get('size', 0),
             'modified': i.get('lastModifiedDateTime', ''),
             'id': i['id'],
             'webUrl': i.get('webUrl', '')} for i in _paged(url)]


def _search_url(drive_id: str, query: str, top: int = 50) -> str:
    """Build the Graph search URL for `q='<query>'`.

    q='...' is an OData string literal: Graph decodes the URL and only then
    parses OData, so a literal apostrophe in `query` breaks out of the quotes
    (e.g. "T&C's ..." -> 400 "Syntax error at position 20"). OData escapes a
    literal quote by doubling it, and that doubling must happen before the
    percent-encoding, not after.
    """
    escaped = (query or '').replace("'", "''")
    return f"{GRAPH}/drives/{drive_id}/root/search(q='{requests.utils.quote(escaped)}')?$top={top}"


def search(drive_id: str, query: str) -> list:
    """Search files inside ONE drive you already know. Returns [{name, path, size, modified, webUrl}].

    Needs a drive_id from sites()+drives() first. If you don't know which site/drive
    the file lives in, use search_all() instead — it searches every accessible site
    and drive in one call, no guessing required.
    """
    url = _search_url(drive_id, query)
    out = []
    try:
        items = _paged(url, limit=50)
    except RuntimeError as e:
        # Graph answers a search with zero hits as 404 itemNotFound instead of
        # 200 + an empty array — a normal "nothing matched", not a failure.
        if 'itemNotFound' in str(e):
            return []
        raise
    for i in items:
        parent = i.get('parentReference', {}).get('path', '')
        parent = parent.split('root:', 1)[-1] if 'root:' in parent else parent
        out.append({'name': i['name'], 'path': parent,
                    'size': i.get('size', 0),
                    'modified': i.get('lastModifiedDateTime', ''),
                    'webUrl': i.get('webUrl', '')})
    return out


# --------------------------------------------------------------------------
# find() — the single entry point
#
# Everything else in this module is an escape hatch. find() exists because the
# alternative is a model picking a site by name and searching only there: on
# 2026-09-28 that path answered "Herta" with 1 file while the tenant held 25,
# including the signed 2026 contract. A caller should never have to choose
# between "search the right place" and "search everywhere" — find() always
# searches everywhere.
# --------------------------------------------------------------------------

# Advice printed by every verb that walks sites by hand. Kept here, not inlined,
# so the wording can't drift between the CLI and the Python API.
EXPLORATORY_ADVICE = (
    "Use find(<query>) first. It searches the whole tenant in one call — every "
    "team site, every document library and every personal OneDrive this token "
    "can see — and returns paths plus site/drive/item ids. The verbs below only "
    "reach the sites sites() can enumerate, which excludes personal OneDrive, so "
    "they can report 'not found' for files that exist. Use them when you "
    "deliberately want to look inside one known place, not to locate a file."
)

_SEARCH_FIELDS = ['name', 'webUrl', 'id', 'size', 'lastModifiedDateTime',
                  'parentReference', 'file', 'folder']

# Graph caps a driveItem search page at 25 hits regardless of what `size` asks for.
_PAGE_SIZE = 25

_DRIVE_CACHE: dict = {}


def _drive_info(drive_id: str) -> dict:
    """Resolve a drive's name and web root, cached per process."""
    if drive_id not in _DRIVE_CACHE:
        info = {'name': '', 'webUrl': '', 'site_name': ''}
        try:
            d = _get_json(f'{GRAPH}/drives/{drive_id}?$select=id,name,webUrl,owner')
            info['name'] = d.get('name', '')
            info['webUrl'] = d.get('webUrl', '')
            owner = d.get('owner', {}).get('user', {}) or d.get('owner', {}).get('group', {})
            info['site_name'] = owner.get('displayName', '')
        except RuntimeError:
            pass  # a drive we can't read metadata for still yields usable hits
        _DRIVE_CACHE[drive_id] = info
    return _DRIVE_CACHE[drive_id]


def _relative_path(item_web_url: str, drive_web_url: str) -> str:
    """Drive-relative path of an item, READ from the two URLs — never guessed.

    A unified-search hit carries no `parentReference.path`, so the path is
    recovered by stripping the drive's own webUrl off the item's webUrl and
    URL-decoding the remainder. That prefix is data returned by Graph, not a
    convention assumed about OneDrive vs team-site URL shapes. When the two
    don't line up this returns '' — an empty path is the honest answer, an
    invented one would be passed straight to get() and fail obscurely.
    """
    if not item_web_url or not drive_web_url:
        return ''
    item = unquote(item_web_url.split('?', 1)[0])
    root = unquote(drive_web_url.split('?', 1)[0]).rstrip('/')
    return item[len(root) + 1:] if item.startswith(root + '/') else ''


def _kind(name: str, resource: dict) -> str:
    """'folder' or 'file'. Search hits carry a `file` facet even on folders, so
    the facet alone can't decide it; the filename extension breaks the tie."""
    if isinstance(resource.get('folder'), dict):
        return 'folder'
    return 'file' if Path((name or '').strip()).suffix else 'folder'


def _refine_kind(kind: str, name: str, path: str) -> str:
    """Promote 'folder' to 'section' for a hit that lives *inside* a container file.

    A OneNote section comes back as an extensionless driveItem whose path ends at
    the .one notebook, not at the section: calling it a folder invites a get() on
    a path that isn't there. Only applies when the path's last segment carries an
    extension the item's own name does not — i.e. the two genuinely disagree.
    """
    if kind != 'folder' or not path:
        return kind
    leaf = path.rstrip('/').rsplit('/', 1)[-1]
    if leaf != name.strip() and Path(leaf).suffix and not Path(name.strip()).suffix:
        return 'section'
    return kind


def _match_rank(name: str, query: str) -> int:
    """0 exact name, 1 name prefix, 2 name contains, 3 matched on content only."""
    n = (name or '').strip().casefold()
    q = (query or '').strip().casefold()
    if not q:
        return 3
    if n == q:
        return 0
    if n.startswith(q):
        return 1
    if q in n:
        return 2
    return 3


def _normalize_hit(hit: dict, query: str) -> dict:
    """Turn one Graph search hit into the record find() returns."""
    r = hit.get('resource', {})
    parent = r.get('parentReference', {})
    name = r.get('name') or ''
    rank = _match_rank(name, query)
    return {
        'name': name.strip(),
        'kind': _kind(name, r),
        'path': '',            # filled in by find() once the drive root is known
        'drive_name': '',      # idem
        'webUrl': r.get('webUrl'),
        'site_id': parent.get('siteId'),
        'drive_id': parent.get('driveId'),
        'item_id': r.get('id'),
        'size': r.get('size', 0),
        'modified': r.get('lastModifiedDateTime', ''),
        'matched_on': 'name' if rank < 3 else 'content',
        'snippet': (hit.get('summary') or '').strip(),
        '_rank': rank,
    }


def _dedupe(entries: list) -> tuple:
    """Drop repeats of the same item. Returns (kept, removed_count).

    Graph can return the same file twice — once per list it is indexed in, and
    again when a query matches both its name and its content. The item id is the
    identity; webUrl is the fallback for hits that arrive without one.
    """
    seen, kept = set(), []
    for e in entries:
        key = e.get('item_id') or ('url', e.get('drive_id'), e.get('webUrl'))
        if key in seen:
            continue
        seen.add(key)
        kept.append(e)
    return kept, len(entries) - len(kept)


def _unified_page(query: str, offset: int, size: int) -> tuple:
    """One page of Graph unified search. Returns (hits, more_available, total)."""
    payload = {
        'requests': [{
            'entityTypes': ['driveItem'],
            'query': {'queryString': query},
            'from': offset,
            'size': size,
            'fields': _SEARCH_FIELDS,
        }]
    }
    data = _request('POST', f'{GRAPH}/search/query', json=payload).json()
    container = (data.get('value', [{}])[0].get('hitsContainers', [{}])[0])
    return (container.get('hits', []),
            bool(container.get('moreResultsAvailable')),
            container.get('total', 0))


def find(query: str, limit: int = 50) -> dict:
    """Locate anything on SharePoint. Tenant-wide, always — no site to pick.

    This is the entry point: call it for every "where is X" question, including
    the ones that name a site out loud ("the contract in Recruitment"), because
    the named site is often not where the file actually sits.

    Returns {query, results, coverage}:

      results  — deduplicated and ordered: exact name matches, then name
                 prefixes, then names containing the query, then files that only
                 matched on their content; most recently modified first inside
                 each group. Every record carries `path`, `drive_id`, `site_id`
                 and `item_id`, so get(), read_xlsx() and ls() can run straight
                 off a hit without a second lookup round.

      coverage — what was actually searched and what the search could not
                 promise. A wrong answer has to stay diagnosable: a caller that
                 reports "not found" must be able to say whether the index was
                 exhausted, truncated at `limit`, or simply silent.
    """
    hits, more, total, offset = [], False, 0, 0
    while len(hits) < limit:
        page, more, total = _unified_page(query, offset, min(_PAGE_SIZE, limit - len(hits)))
        hits.extend(page)
        offset += len(page)
        if not page or not more:
            break

    entries = [_normalize_hit(h, query) for h in hits[:limit]]
    entries, duplicates = _dedupe(entries)

    # Stable two-pass sort: newest first, then grouped by match quality.
    entries.sort(key=lambda e: e.get('modified') or '', reverse=True)
    entries.sort(key=lambda e: e['_rank'])

    for e in entries:
        info = _drive_info(e['drive_id']) if e.get('drive_id') else {}
        e['drive_name'] = info.get('name', '')
        e['path'] = _relative_path(e.get('webUrl'), info.get('webUrl', ''))
        e['kind'] = _refine_kind(e['kind'], e['name'], e['path'])
        e.pop('_rank', None)

    drives_spanned = sorted({e['drive_id'] for e in entries if e.get('drive_id')})
    sites_spanned = sorted({e['site_id'] for e in entries if e.get('site_id')})

    return {
        'query': query,
        'results': entries,
        'coverage': {
            'method': 'graph-unified-search (POST /search/query, entityTypes=driveItem)',
            'scope': ('whole tenant index — every team site, document library and '
                      'personal OneDrive this token can see, without naming any of them'),
            'returned': len(entries),
            'duplicates_removed': duplicates,
            'requested_limit': limit,
            'truncated_at_limit': len(hits) >= limit and more,
            'more_available': more,
            'index_total_reported': total,
            'sites_with_hits': len(sites_spanned),
            'drives_with_hits': len(drives_spanned),
            'drive_ids': drives_spanned,
            'limits': [
                'Only items Microsoft Graph has indexed AND this token may see are '
                'returned: an empty result means "not found or not indexed", never '
                'proof the file does not exist.',
                'index_total_reported is the relevance engine\'s own count, inflated '
                'by fuzzy and content matches — it is not a count of files named '
                'like the query. Trust `returned`.',
                'Hits with matched_on="content" contain the query inside the '
                'document, not in the filename.',
                'A hit whose `path` is empty sits in a drive whose root URL could '
                'not be resolved: use item_id with get_item() instead of path.',
            ],
        },
    }


def search_all(query: str, top: int = 25) -> list:
    """Flat tenant-wide result list. Thin wrapper over find(), kept for callers
    written against 1.3. Prefer find(): same search, plus paths and coverage."""
    return find(query, limit=top)['results']


def browse(site: str = None) -> dict:
    """Exploratory walk: the sites you can enumerate, then one site's drives.

    This is the guessing path — the one that answers "not found" for files that
    exist somewhere it never looked. It is kept because sometimes you genuinely
    want to look inside a specific site by eye. It therefore leads with
    EXPLORATORY_ADVICE: locating a file is find()'s job, not this one's.

    browse()            -> {advice, sites, next}
    browse("GR Team")   -> {advice, site, drives, next}   (id or name substring)
    """
    all_sites = sites()
    if not site:
        return {
            'advice': EXPLORATORY_ADVICE,
            'sites': all_sites,
            'note': ('This list excludes personal OneDrive drives, which find() '
                     'does reach. Sites listed here are not the whole tenant.'),
            'next': 'browse("<site name or id>") for its document libraries, '
                    'then ls(drive_id) or search(drive_id, query).',
        }
    needle = site.casefold()
    match = next((s for s in all_sites if s['id'] == site), None) \
        or next((s for s in all_sites if needle in s['name'].casefold()), None)
    if not match:
        return {
            'advice': EXPLORATORY_ADVICE,
            'error': f'No enumerable site matches {site!r}.',
            'sites': [s['name'] for s in all_sites],
            'next': f'find("{site}") searches the tenant without needing a site name.',
        }
    return {
        'advice': EXPLORATORY_ADVICE,
        'site': match,
        'drives': drives(match['id']),
        'next': 'ls(drive_id) to walk a library, search(drive_id, query) to search '
                'only inside it, or find(query) to search everywhere.',
    }


def get(drive_id: str, path: str, local_dest: str = None) -> str:
    """Download a file. Returns the local path written."""
    resp = _request('GET', _item_url(drive_id, path) + '/content')
    dest = Path(local_dest) if local_dest else Path('storage/sharepoint') / Path(path).name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    return str(dest)


def get_item(drive_id: str, item_id: str, local_dest: str = None) -> str:
    """Download a file by its item id — the id find() returns. Use this when a
    hit's `path` came back empty, or when the path has characters you'd rather
    not round-trip through URL quoting. Returns the local path written."""
    meta = _get_json(f'{GRAPH}/drives/{drive_id}/items/{item_id}?$select=id,name')
    resp = _request('GET', f'{GRAPH}/drives/{drive_id}/items/{item_id}/content')
    dest = Path(local_dest) if local_dest else Path('storage/sharepoint') / meta.get('name', item_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    return str(dest)


def _parse_xlsx(local_path: str, sheet: str = None, max_rows: int = 200) -> dict:
    """Read headers + rows from a local .xlsx file. Pure function, no network.

    Returns {sheet, headers, rows, total_rows, truncated}. `total_rows` counts
    data rows (header excluded); `truncated` is True when the sheet has more
    rows than `max_rows` — the brain is a notebook, not an archive, so only
    the first `max_rows` data rows come back, never the whole file.
    """
    try:
        import openpyxl
    except ImportError as e:
        raise RuntimeError(
            "openpyxl not installed — this brain image lacks the Excel library. "
            "Fix belongs in abchat-infra's Dockerfile.brain (image rebuild + "
            "redeploy), never a live pip install (lost on next container restart)."
        ) from e

    wb = openpyxl.load_workbook(local_path, data_only=True, read_only=True)
    try:
        ws = wb[sheet] if sheet else wb.active
        rows_iter = ws.iter_rows(values_only=True)
        try:
            headers = list(next(rows_iter))
        except StopIteration:
            return {'sheet': ws.title, 'headers': [], 'rows': [],
                    'total_rows': 0, 'truncated': False}

        rows = []
        total_rows = 0
        for row in rows_iter:
            total_rows += 1
            if len(rows) < max_rows:
                rows.append(list(row))

        return {
            'sheet': ws.title,
            'headers': headers,
            'rows': rows,
            'total_rows': total_rows,
            'truncated': total_rows > max_rows,
        }
    finally:
        wb.close()


def read_xlsx(drive_id: str, path: str, sheet: str = None, max_rows: int = 200) -> dict:
    """Download an Excel file from SharePoint and return headers + rows.

    Downloads into `storage/tmp/` (working copy, not the persisted
    `storage/sharepoint/` used by `get()`) then parses it. See `_parse_xlsx`
    for the return shape and the truncation rule.
    """
    dest = Path('storage/tmp') / Path(path).name
    dest.parent.mkdir(parents=True, exist_ok=True)
    get(drive_id, path, str(dest))
    return _parse_xlsx(str(dest), sheet=sheet, max_rows=max_rows)


def put(drive_id: str, local_file: str, path: str) -> dict:
    """Upload a file (<4MB simple upload). Returns {name, webUrl, size}."""
    data = Path(local_file).read_bytes()
    if len(data) > 4 * 1024 * 1024:
        raise RuntimeError('File >4MB: simple upload not supported (v1). Split or ask for upload-session support.')
    resp = _request('PUT', _item_url(drive_id, path) + '/content',
                    data=data, headers={'Content-Type': 'application/octet-stream'})
    i = resp.json()
    return {'name': i.get('name'), 'webUrl': i.get('webUrl'), 'size': i.get('size')}


def _main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd, rest = args[0], args[1:]
    # Verbs that walk sites by hand. Locating a file is find()'s job, so they say
    # so on stderr before answering — stdout stays parseable JSON either way.
    if cmd in ('browse', 'sites', 'drives', 'search'):
        print(f'[sharepoint] {EXPLORATORY_ADVICE}', file=sys.stderr)
    try:
        if cmd == 'find':
            out = find(rest[0], int(rest[1]) if len(rest) > 1 else 50)
        elif cmd == 'browse':
            out = browse(rest[0] if rest else None)
        elif cmd == 'sites':
            out = sites(rest[0] if rest else '*')
        elif cmd == 'drives':
            out = drives(rest[0])
        elif cmd == 'ls':
            out = ls(rest[0], rest[1] if len(rest) > 1 else '')
        elif cmd == 'search':
            out = search(rest[0], rest[1])
        elif cmd in ('search-all', 'searchall'):
            out = search_all(rest[0])
        elif cmd == 'get':
            out = get(rest[0], rest[1], rest[2] if len(rest) > 2 else None)
        elif cmd in ('get-item', 'get_item'):
            out = get_item(rest[0], rest[1], rest[2] if len(rest) > 2 else None)
        elif cmd == 'put':
            out = put(rest[0], rest[1], rest[2])
        elif cmd == 'read_xlsx':
            sheet = rest[2] if len(rest) > 2 and rest[2] else None
            max_rows = int(rest[3]) if len(rest) > 3 else 200
            out = read_xlsx(rest[0], rest[1], sheet=sheet, max_rows=max_rows)
        else:
            print(__doc__)
            return
    except IndexError:
        print(__doc__)
        sys.exit(1)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    _main()
