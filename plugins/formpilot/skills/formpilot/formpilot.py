"""
FormPilot admin API — list forms, read submissions, create/clone/design forms
without the web panel. Shared skill: one copy per installation, a symlink in
every brain, each brain with its own token in `.env`.

Authority is the token's, nothing more: the token belongs to the brain's owner
and carries their FormPilot role. Reads work for any role; writes
(create/update/toggle/clone) need the admin role — the API enforces it, this
wrapper just translates the 403 into a PermissionError.

A form's config is `{"sections": [{"type", "title", "fields": [...]}]}` —
fields sit inside sections, never flat on config. `create_form()`'s default
(no config, no clone_from) still sets `sections: []`: the public candidate
page does `config['sections']` with no null-coalesce, an empty/missing key
there breaks the page on open.

Design endpoint, not just CRUD: `list_modules()` returns every field block
already used across all forms and sections (deduplicated by name+type+label,
each tagged with which form/section it came from) — the raw material to
design a new form from pieces of the existing ones instead of retyping every
field. `clone_form()` / `clone_from=` on `create_form()` do the same at form
level: start from a sibling form and edit from there.

No delete function on purpose — the API has no DELETE route. A form is
opened/closed, never removed, by design (destructive actions stay a human
action in the web admin).

Env: FORMPILOT_API_TOKEN + FORMPILOT_API_URL in the brain's `.env`. The lookup
walks up from this file's *unresolved* path (`.absolute()`, not `.resolve()`):
through the shared-skill symlink that lands on the brain root, where `.env`
lives; resolving would land in `shared/skills/`, where it does not.
"""

import os
from pathlib import Path
from typing import Optional

import requests


def _get_env(key: str) -> str:
    val = os.environ.get(key)
    if val:
        return val
    # Walk up from this file and from cwd — mirrors skills/hiresweet/hiresweet.py.
    candidates = [Path(__file__).absolute().parent.parent.parent.parent / ".env"]
    cwd = Path.cwd()
    candidates += [d / ".env" for d in [cwd, *cwd.parents][:5]]
    for env_file in candidates:
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip()
    raise ValueError(f"{key} not found in env or .env.")


def _base_url() -> str:
    try:
        return _get_env("FORMPILOT_API_URL").rstrip("/")
    except ValueError:
        return "https://forms.grworktech.com"


def _headers() -> dict:
    return {"Authorization": f"Bearer {_get_env('FORMPILOT_API_TOKEN')}",
            "Accept": "application/json"}


def _call(method: str, path: str, **kwargs) -> dict:
    r = requests.request(method, f"{_base_url()}/api/v1{path}",
                         headers=_headers(), timeout=20, **kwargs)
    if r.status_code == 401:
        raise ValueError("FormPilot rejected the token — expired or revoked, "
                          "get a new one from /admin/api-tokens.")
    if r.status_code == 403:
        raise PermissionError(r.json().get("message", "Admin role required for this."))
    r.raise_for_status()
    return r.json()


# ── Read ───────────────────────────────────────────────────────────────

def list_forms() -> list:
    """All forms with status and submission count."""
    return _call("GET", "/forms")["forms"]


def get_form(form_id: int) -> dict:
    """One form, full config included."""
    return _call("GET", f"/forms/{form_id}")


def list_submissions(form_id: int, search: Optional[str] = None, page: int = 1) -> dict:
    """Paginated submissions for one form. `search` matches inside the data,
    case-insensitive. Returns {form, data, meta} — meta.total is the count."""
    params = {"page": page}
    if search:
        params["q"] = search
    return _call("GET", f"/forms/{form_id}/submissions", params=params)


def list_modules() -> list:
    """Every field block already used across all forms, deduplicated by
    (name, type, label). Each entry also carries source_form_id/title, so you
    can see which form a block came from before reusing it."""
    return _call("GET", "/forms/modules")["modules"]


# ── Write (admin role required) ──────────────────────────────────────────

def create_form(title: str, description: str = None, config: dict = None,
                clone_from: int = None, status: str = "closed") -> dict:
    """Create a form. Either pass `config` ({"fields": [...], ...}) built from
    list_modules() blocks, or `clone_from` an existing form's id to start
    from its fields, or neither for an empty form. Always starts `closed`
    unless you pass status='open'."""
    body = {"title": title, "status": status}
    if description:
        body["description"] = description
    if config is not None:
        body["config"] = config
    if clone_from is not None:
        body["clone_from"] = clone_from
    return _call("POST", "/forms", json=body)


def clone_form(form_id: int, title: str) -> dict:
    """Copy a form's fields under a new title. Always starts closed."""
    return _call("POST", f"/forms/{form_id}/clone", json={"title": title})


def update_form(form_id: int, title: str = None, description: str = None,
                config: dict = None, **extra) -> dict:
    """Partial update — only the fields you pass change. `config` replaces
    the whole config (fetch with get_form() first if you're editing, not
    rebuilding, a form's fields)."""
    body = {k: v for k, v in {"title": title, "description": description,
                              "config": config, **extra}.items() if v is not None}
    return _call("PUT", f"/forms/{form_id}", json=body)


def toggle_status(form_id: int) -> dict:
    """Flip open<->closed. Returns the form with its new status."""
    return _call("POST", f"/forms/{form_id}/toggle")


# ── CLI ──────────────────────────────────────────────────────────────────
# Read-only from the command line, so a viewer can answer "how many applied
# to Fairtrade?" without writing Python. Writes stay in Python on purpose:
# they need the admin role and a human reading what they're about to do.

def _strip(html: str) -> str:
    import re
    return re.sub(r"<[^>]+>", " ", html or "").strip()


def _find_form(ref: str) -> dict:
    """Accept an id, a slug or a piece of the title ("fairtrade")."""
    forms = list_forms()
    if ref.isdigit():
        hits = [f for f in forms if f["id"] == int(ref)]
    else:
        needle = ref.lower()
        hits = [f for f in forms if needle in (f.get("slug") or "").lower()
                or needle in (f.get("title") or "").lower()]
    if len(hits) != 1:
        names = ", ".join(f"{f['id']} {f['title']}" for f in hits or forms)
        raise SystemExit(f"'{ref}' matches {len(hits)} forms — be more specific: {names}")
    return hits[0]


def _main(argv: list) -> None:
    import json
    cmd = argv[0] if argv else "forms"
    if cmd == "forms":
        for f in list_forms():
            print(f"{f['id']:>3}  {f['status']:<6}  {f['submissions_count']:>4} submissions  {f['title']}")
    elif cmd == "show" and len(argv) > 1:
        f = _find_form(argv[1])
        print(json.dumps({k: v for k, v in f.items() if k != "config"}, indent=2, ensure_ascii=False))
        for s in (f.get("config") or {}).get("sections", []):
            print(f"\n[{s.get('type')}] {s.get('title')}")
            for fld in s.get("fields", []):
                print(f"   - {fld.get('name')} ({fld.get('type')}){' *' if fld.get('required') else ''}: {_strip(fld.get('label'))[:70]}")
    elif cmd == "submissions" and len(argv) > 1:
        f = _find_form(argv[1])
        q = argv[2] if len(argv) > 2 else None
        res = list_submissions(f["id"], search=q)
        print(f"{res['meta']['total']} submissions on «{f['title']}»" + (f" matching '{q}'" if q else ""))
        for s in res["data"]:
            d = s.get("data") or {}
            if isinstance(d, str):
                d = json.loads(d)
            who = " ".join(x for x in (d.get("first_name"), d.get("surname") or d.get("last_name")) if x) or d.get("full_name") or "?"
            print(f"   {str(s.get('submitted_at') or s.get('created_at'))[:16]}  {who:<28} {d.get('email', '')}")
    elif cmd == "modules":
        for m in list_modules():
            print(f"{m['type']:<10} {m['name']:<28} {_strip(m.get('label'))[:50]}  ← form {m['source_form_id']}")
    else:
        raise SystemExit("usage: formpilot.py forms | show <form> | submissions <form> [search] | modules")


if __name__ == "__main__":
    import sys
    _main(sys.argv[1:])
