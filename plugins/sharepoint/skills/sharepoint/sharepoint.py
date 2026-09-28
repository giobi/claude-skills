#!/usr/bin/env python3
"""
SharePoint wrapper via Microsoft Graph.

Reuses the O365 OAuth token from the email skill (same .env, same refresh flow).
The app registration already carries Sites.ReadWrite.All + Files.ReadWrite.All.

CLI:
    sharepoint.py sites [query]              # list/search SharePoint sites
    sharepoint.py drives <site-id>           # document libraries of a site
    sharepoint.py ls <drive-id> [path]       # list folder content
    sharepoint.py search <drive-id> <query>  # search files inside a drive
    sharepoint.py search-all <query>         # search files tenant-wide (every accessible site/drive)
    sharepoint.py get <drive-id> <path> [local_dest]   # download a file
    sharepoint.py put <drive-id> <local_file> <path>   # upload a file (<4MB)
    sharepoint.py read_xlsx <drive-id> <path> [sheet] [max_rows]  # headers + rows of an Excel file

Python:
    import sys; sys.path.insert(0, '.claude/skills/sharepoint')
    from sharepoint import sites, drives, ls, search, search_all, get, put, read_xlsx
"""

import json
import sys
from pathlib import Path

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


def search_all(query: str, top: int = 25) -> list:
    """Search files across EVERY SharePoint site and drive you can access, in one call.

    Uses Microsoft Graph unified search (POST /search/query), unlike search()
    which needs a drive_id picked in advance by guessing the right site name.
    Use this first when you don't already know where a file lives — it is the
    default entry point, not a fallback. Returns
    [{name, webUrl, site_id, drive_id, item_id, size}].
    """
    payload = {
        'requests': [{
            'entityTypes': ['driveItem'],
            'query': {'queryString': query},
            'size': top,
            'fields': ['name', 'webUrl', 'id', 'size', 'parentReference'],
        }]
    }
    resp = _request('POST', f'{GRAPH}/search/query', json=payload)
    data = resp.json()
    hits = (data.get('value', [{}])[0]
                .get('hitsContainers', [{}])[0]
                .get('hits', []))
    out = []
    for h in hits:
        r = h.get('resource', {})
        parent = r.get('parentReference', {})
        out.append({
            'name': r.get('name'),
            'webUrl': r.get('webUrl'),
            'site_id': parent.get('siteId'),
            'drive_id': parent.get('driveId'),
            'item_id': r.get('id'),
            'size': r.get('size', 0),
        })
    return out


def get(drive_id: str, path: str, local_dest: str = None) -> str:
    """Download a file. Returns the local path written."""
    resp = _request('GET', _item_url(drive_id, path) + '/content')
    dest = Path(local_dest) if local_dest else Path('storage/sharepoint') / Path(path).name
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
    try:
        if cmd == 'sites':
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
