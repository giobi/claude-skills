#!/usr/bin/env python3
"""
share.py — the driver behind /artifact: resolves addresses for the folders in this
brain's `public/`, and publishes or revokes them, on any install of the fleet.

An artifact has TWO addresses, and they are not interchangeable:

  * internal  `{install}/artifact/{brain}/{folder}/` — auth-gated. Only people who
    logged into the village can open it. No expiry, nothing exposed outside.
    This is the DEFAULT address: `share.py link`.
  * token     `{install}/share/{token}/…` — opaque and time-limited, readable by
    ANYONE holding the link. This is `share.py publish`, and it is a deliberate
    second step, not what you hand out by reflex.

Neither address is ever composed blind. `link` checks the folder exists on disk and
probes the route on this install; `publish` returns whatever URL the app minted. A
plausible dead link costs more than an honest "I don't have one".

Every install has its own host and its own plumbing, so the endpoint is never
hardcoded here — it is DERIVED (boot/local.yaml → skill config → env → the
container's INSTANCE_HOST).

Token authentication is proof-by-filesystem: we write a nonce into
`storage/.share-request.json`, then POST {brain, nonce} to the API; only something
able to write inside this brain could have created it. The file is one-shot.

Usage:
    python3 share.py link    [folder]          # internal address — use this by default
    python3 share.py list                      # published + unpublished, with addresses
    python3 share.py publish [folder] [--days N] [--password PW]
    python3 share.py revoke  <folder>
    python3 share.py doctor                    # what is actually alive on THIS install
    ... [--json]                               # raw output for scripts

`folder` is relative to `public/`. Empty = the whole of `public/`.
Exits 1 with a message on stderr when something fails: never print a URL for a call
that did not succeed.
"""

import argparse
import json
import os
import re
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


# ---------------------------------------------------------------- brain root

def find_brain_root() -> Path:
    """
    The root of the brain we are operating on.

    This skill is installed as a SYMLINK into `<brain>/.claude/skills/artifact`,
    pointing at one shared copy. So `Path(__file__).resolve()` lands in
    `/var/abchat/shared/skills/…` — the shared tree, not the brain — and counting
    parent directories from there gives the wrong root for every brain at once.
    Hence: BRAIN_ROOT if declared, otherwise walk up from the working directory,
    and only fall back to the file's own location for a non-symlinked install.
    """
    def looks_like_brain(p: Path) -> bool:
        return (p / "boot").is_dir() or (p / "CLAUDE.md").is_file()

    declared = os.getenv("BRAIN_ROOT", "").strip()
    if declared:
        p = Path(declared)
        if looks_like_brain(p):
            return p.resolve()

    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if looks_like_brain(candidate):
            return candidate

    # Real directory install (not a symlink): .claude/skills/artifact/share.py
    here = Path(__file__).resolve()
    if len(here.parents) > 3 and looks_like_brain(here.parents[3]):
        return here.parents[3]

    sys.exit(
        "Cannot locate the brain root: no BRAIN_ROOT, and the working directory is "
        "not inside a brain. Run this from the brain root, or export BRAIN_ROOT."
    )


ROOT = find_brain_root()
ENV_PATH = ROOT / ".env"
LOCAL_YAML = ROOT / "boot" / "local.yaml"       # ← infrastructure is declared HERE
CONFIG_PATHS = [ROOT / "wiki" / "skills" / "artifact.md",
                ROOT / "wiki" / "skills" / "public.md"]     # legacy name
REQUEST_FILE = ROOT / "storage" / ".share-request.json"
UA = "abchat-brain-share/1.0"                   # Cloudflare returns 1010 to urllib's default
BROWSER_UA = "Mozilla/5.0 (compatible; brain-share/1.0)"
TIMEOUT = 30


# ---------------------------------------------------------------- sources

def read_env(key: str) -> str:
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip("\"'")
    return os.getenv(key, "")


def config() -> dict:
    """Frontmatter of wiki/skills/artifact.md (falling back to public.md), no PyYAML needed."""
    for path in CONFIG_PATHS:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("---"):
            continue
        block = text.split("---", 2)[1]
        try:
            import yaml
            return yaml.safe_load(block) or {}
        except Exception:
            out = {}
            for line in block.splitlines():
                m = re.match(r"^([a-z_]+):\s*(.+?)\s*$", line)
                if m:
                    out[m.group(1)] = m.group(2).strip("\"'")
            return out
    return {}


def infra() -> dict:
    """
    The `public:` section of `boot/local.yaml` — the DECLARATION of how a page
    becomes reachable on this install.

    Why here and nowhere else: in the brain protocol, infrastructure is decided by
    `boot/local.yaml` (machine/environment) and `boot/domain.md` (contract), not by
    a skill's config and not by the container's environment. `wiki/skills/artifact.md`
    only holds skill options (templates, default lifetime). Deriving the host from
    the environment was the very class of error this skill exists to close: an
    infrastructural fact reconstructed from clues instead of read where it is written.
    """
    if not LOCAL_YAML.exists():
        return {}
    try:
        import yaml
        data = yaml.safe_load(LOCAL_YAML.read_text(encoding="utf-8", errors="replace")) or {}
    except Exception:
        return {}
    pub = data.get("public")
    return pub if isinstance(pub, dict) else {}


def instance_host() -> str:
    """Install host: declared in local.yaml, environment only as a fallback."""
    declared = str(infra().get("base_url") or "").strip()
    if declared:
        return urllib.parse.urlsplit(declared if "//" in declared else f"https://{declared}").netloc
    return os.getenv("INSTANCE_HOST", "").strip()


def share_api_candidates() -> list:
    """
    /api/share/cli endpoints to try, in order. Returns [(url, verify_tls)].

    Fleet installs are not reachable the same way and ONE candidate is not enough:
      - avocado: INSTANCE_HOST (avocado.abchat.it) 301s to the canonical host → ok
      - grbrain: INSTANCE_HOST (grbrain.com) answers directly → ok
      - emibrain: on-prem, the public host is NOT reachable from the container
        (timeout); the only way in is the internal nginx `{INSTANCE_ID}-nginx`,
        whose certificate obviously does not match the container name.

    TLS verification is off for that last hop: it is a container→container jump on
    the install's docker network, and the alternative is that publishing simply
    does not work there.

    ⚠️ The app builds the returned URL from the REQUEST host, not from APP_URL:
    knocking on `emi-nginx` yields `https://emi-nginx/share/…`, a container name
    nobody can open. Hence the canonical `Host:` header on the internal candidate,
    plus validation of whatever URL comes back (see `canonical_host()`, `check_url()`).
    """
    out = []
    inf = infra()
    # 1. declared in boot/local.yaml — the source of truth
    for key, verify in (("share_api", True), ("share_api_internal", False)):
        v = str(inf.get(key) or "").strip()
        if v and v.lower() not in ("null", "none", "~"):
            out.append((v, verify))
    # 2. fallbacks for brains whose local.yaml does not declare the section yet
    if not out:
        explicit = str(config().get("share_api") or "").strip() or os.getenv("SHARE_API_URL", "").strip()
        if explicit:
            out.append((explicit, True))
        host = instance_host()
        if host:
            out.append((f"https://{host}/api/share/cli", True))
        iid = os.getenv("INSTANCE_ID", "").strip()
        if iid:
            out.append((f"https://{iid}-nginx/api/share/cli", False))
    if not out:
        sys.exit(
            "Cannot derive the publishing endpoint.\n"
            "Declare it in boot/local.yaml:\n\n"
            "public:\n"
            "  mode: share-token\n"
            "  base_url: https://<public host of the install>\n"
            "  share_api: https://<public host of the install>/api/share/cli\n"
        )
    seen, uniq = set(), []
    for url, verify in out:
        if url not in seen:
            seen.add(url)
            uniq.append((url, verify))
    return uniq


def slug_candidates() -> list:
    """
    The slug the app knows this brain by. It varies per install: on some it is in
    .env, on others the manifest carries the UID instead of the slug. Tried in order.
    """
    out = []
    manifest_slug = None
    manifest = ROOT / "manifest.json"
    if manifest.exists():
        try:
            manifest_slug = json.loads(manifest.read_text()).get("slug")
        except Exception:
            pass

    for v in (str(infra().get("brain_slug") or "").strip(),     # declared in local.yaml, wins
              str(config().get("brain_slug") or "").strip(),    # legacy: skill config
              read_env("WORKSPACE_SLUG"),
              read_env("BRAIN_SLUG"),
              manifest_slug,
              # the brain's own folder name — but inside the container the mount is
              # always called "data", which is never a slug: not worth trying.
              ROOT.name if ROOT.name != "data" else ""):
        if v and v not in out:
            out.append(v)
    if not out:
        sys.exit("Cannot determine the brain slug (no config, no .env, no manifest.json).")
    return out


# ---------------------------------------------------------------- the call

def canonical_host() -> str:
    """
    The host USERS reach this install by — the one that must appear in links.
    Declared as `public.base_url` in boot/local.yaml. Container environments are not
    trustworthy: on emibrain, 19 of 25 still say `v2.emibrain.it`, a dead vhost.
    That is why `instance_host()` reads local.yaml first and the environment second.
    """
    return instance_host()


def check_url(url: str) -> str:
    """
    Flag unusable URLs instead of passing them off as good: a link pointing at the
    install's internal nginx is reachable by no user at all.
    Returns an empty string when the URL is fine, otherwise the reason.
    """
    host = urllib.parse.urlsplit(url).netloc
    iid = os.getenv("INSTANCE_ID", "").strip()
    if iid and host.startswith(f"{iid}-"):
        return (f"the app returned a link on the internal host `{host}`, which nobody "
                f"can open. Declare `public.base_url: https://<public host>` in "
                f"boot/local.yaml.")
    return ""


class Unreachable(Exception):
    """The endpoint does not answer (network/DNS/TLS): move on to the next candidate."""


def post(url: str, payload: dict, verify: bool = True, host: str = "", _redirects: int = 3):
    """POST JSON. Follows 3xx KEEPING the POST (urllib would downgrade it to GET:
    on avocado INSTANCE_HOST 301s to the canonical host). `host` forces the Host
    header, so the app builds links with the public name and not with the name of
    the container we knocked on."""
    headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": UA}
    if host:
        headers["Host"] = host
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    handlers = [NoRedirect()]
    if not verify:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        handlers.append(urllib.request.HTTPSHandler(context=ctx))
    opener = urllib.request.build_opener(*handlers)

    try:
        with opener.open(req, timeout=TIMEOUT) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 307, 308) and _redirects > 0:
            loc = e.headers.get("Location")
            if loc:
                return post(urllib.parse.urljoin(url, loc), payload, verify, host, _redirects - 1)
        body = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"error": f"HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        raise Unreachable(f"{url}: {e}")


def call(action: str, **payload) -> dict:
    """
    Try every candidate endpoint and, for each, every plausible slug: first 200 wins.
    An unreachable endpoint is not fatal — it is the normal case on an install whose
    public host cannot be reached from inside.
    """
    errors = []
    canon = canonical_host()
    for api, verify in share_api_candidates():
        # Canonical Host header only when knocking on a service (internal) endpoint:
        # on public endpoints the host is already the right one.
        host = canon if (not verify and canon) else ""
        for slug in slug_candidates():
            nonce = secrets.token_urlsafe(30)
            REQUEST_FILE.parent.mkdir(parents=True, exist_ok=True)
            REQUEST_FILE.write_text(json.dumps({"nonce": nonce, "action": action, **payload}))
            try:
                status, body = post(api, {"brain": slug, "nonce": nonce}, verify, host)
            except Unreachable as e:
                errors.append(str(e))
                break                      # dead endpoint: no point trying other slugs
            finally:
                REQUEST_FILE.unlink(missing_ok=True)
            if status == 200:
                return body
            errors.append(f"{api} [{slug}]: {body.get('error', status)}")
    return {"error": "; ".join(errors[-3:]) or "no endpoint reachable"}


# ------------------------------------------------------ the folder argument

def normalize_folder(folder: str) -> str:
    """
    What the caller meant by `folder`, which is relative to public/.

    Writing `public/my-page` instead of `my-page` is the commonest way this tool is
    mis-called: the prefix is right there in every path the caller has just been
    handling on disk, so it comes along for the ride. The server then looks for
    public/public/my-page and answers `folder not found` — and a model reading that
    concludes the publishing service is broken rather than that its own argument was.
    Accepting both spellings removes the failure instead of explaining it.

    The literal path wins when it exists on disk, so a brain that really does have a
    folder named `public` inside public/ keeps working. Only when the literal path is
    absent AND the stripped one is present do we read the prefix as a slip. Anything
    else comes back as typed, so the error can talk about what was actually asked.
    """
    rel = folder.strip().strip("/")
    if not rel:
        return ""
    base = ROOT / "public"
    if (base / rel).is_dir():
        return rel
    stripped = rel
    while stripped.startswith("public/"):
        stripped = stripped[len("public/"):].strip("/")
    if stripped and stripped != rel and (base / stripped).is_dir():
        return stripped
    return rel


def folder_hint(folder: str) -> str:
    """
    The sentence that turns a bare `folder not found` into something the caller can
    act on: the rule, the spelling that would have worked, and what is actually there.

    An error that states only the outcome leaves the reader to guess the cause, and
    the cheapest guess is always "the service is broken".
    """
    rel = folder.strip().strip("/")
    bare = rel
    while bare.startswith("public/"):
        bare = bare[len("public/"):].strip("/")

    if bare and bare != rel:
        hint = (f"`folder` is relative to public/, so this doubles the prefix: "
                f"pass `{bare}`, not `{rel}`.")
    else:
        hint = ("`folder` is relative to public/ — pass `my-page`, not "
                "`public/my-page` and not an absolute path.")

    available = folders()
    if available:
        shown = available[:12]
        hint += ("  Folders in public/: " + ", ".join(shown)
                 + (f", … (+{len(available) - len(shown)} more)"
                    if len(available) > len(shown) else ""))
    else:
        hint += "  public/ currently holds no folders."
    return hint


def missing_folder_note(error: str, folder: str) -> str:
    """
    The hint to append to a SERVER error, or "" when the server was complaining about
    something else entirely.

    Only `folder not found` earns it. Appending the folder lecture to an expired
    token or an unreachable endpoint would send the reader after the wrong cause,
    which is the very failure this is here to stop.
    """
    if "folder not found" not in (error or "").lower():
        return ""
    return "\n" + folder_hint(folder)


# -------------------------------------------------- internal address (artifact)

def index_missing(rel: str) -> str:
    """
    The note to hand back when a folder cannot produce a usable address because it has
    no `index.html`, or "" when it has one.

    Mirrors SharePublisher::indexMancante on the app side, which is what makes
    `publish` answer 422 on the same folder. Without it `link` was the one door in
    that answered with a URL instead of a reason — and a URL is what gets announced.
    """
    base = ROOT / "public"
    abs_dir = base / rel if rel else base
    if (abs_dir / "index.html").is_file():
        return ""

    where = f'the folder public/{rel}/' if rel else "the root of public/"
    note = (f"{where} has no index.html, so the address would 404. "
            "The route serves index.html only: generate one (an index.md is not served) "
            "and run this again.")

    # Same hint the app gives: a sibling that WOULD work is usually what was meant.
    usable = sorted(d.name for d in abs_dir.iterdir()
                    if d.is_dir() and (d / "index.html").is_file()) if abs_dir.is_dir() else []
    if usable:
        prefix = f"{rel}/" if rel else ""
        note += " Sub-folders that do have one: " + ", ".join(prefix + u for u in usable) + "."
    return note


def internal_url(folder: str = "") -> tuple:
    """
    The address a LOGGED-IN user opens their artifact with, without publishing it.

    It is Laravel's `/artifact/{brain}/{path}` route: gated behind login, visible to
    people in the village, with the share bar for the owner. No expiry, nothing
    exposed to the outside.

    Returns (url, note). An empty `url` means it is not available on this install and
    `note` says why. An unprobed address is never returned: a plausible dead link
    costs more than an honest "I don't have one".
    """
    # A protected route answers 302 (go to login) for ANY path, existing or not. So
    # the HTTP probe tells us whether the ROUTE exists on this install, never whether
    # the FOLDER exists: that is checked on disk, or we end up handing out plausible
    # dead links — exactly what rule zero forbids.
    rel_check = normalize_folder(folder)
    if rel_check and not (ROOT / "public" / rel_check).is_dir():
        return "", (f"the folder public/{rel_check}/ does not exist: there is nothing "
                    f"to open. {folder_hint(folder)}")

    # Existing is not enough: the route serves index.html and ONLY index.html — an
    # index.md sitting there is a 404 with a plausible URL in front of it. Same check
    # the app already applies before publishing (SharePublisher::indexMancante),
    # applied here too so `link` cannot hand out an address that is born dead.
    if note := index_missing(rel_check):
        return "", note

    host = canonical_host().rstrip("/")
    if not host:
        return "", ("this install does not declare `public.base_url` in boot/local.yaml, "
                    "so there is no host to build the address from")
    # Without a scheme it is not a link: the terminal will not make it clickable and
    # urllib refuses it. The host declared in local.yaml may be bare.
    if not host.startswith(("http://", "https://")):
        host = "https://" + host
    slug = slug_candidates()[0]
    rel = rel_check
    for prefix in ("artifact", "public"):       # `public` = installs not yet updated
        url = f"{host}/{prefix}/{slug}/" + (f"{rel}/" if rel else "")
        status = probe(url)
        # A 302 to the login page is the RIGHT answer: the route exists and is protected.
        if status in (200, 301, 302, 303, 307, 308):
            return url, ""
        if status == 404:
            continue                            # prefix absent: try the next one
        return "", f"the route answered {status}"
    return "", ("this install exposes neither /artifact/ nor /public/: "
                "its village code is not up to date")


def probe(url: str) -> int:
    """HEAD without following redirects: we want the status code, not the page."""
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    opener = urllib.request.build_opener(NoRedirect)
    # Cloudflare answers 403 to urllib's user agent: without this header every route
    # would look forbidden and we would never hand out the internal link.
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": BROWSER_UA})
    try:
        with opener.open(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def folders() -> list:
    """
    The folders present in public/, PUBLISHED OR NOT.

    `list` on its own only ever showed what had a token: a folder that was never
    published did not exist as far as the skill was concerned. And that is half the
    reason publishing looked like the only way to produce a link.
    """
    base = ROOT / "public"
    if not base.is_dir():
        return []
    return sorted(d.name for d in base.iterdir()
                  if d.is_dir() and not d.name.startswith(".") and d.name != "template")


# ---------------------------------------------------------------- output

def show(rows: list) -> None:
    published = {r.get("folder") or "" for r in rows}
    if not rows:
        print("Nothing published: no page of this brain is reachable from outside. "
              "(That does not mean there are no artifacts — see below.)")
    for r in rows:
        bad = check_url(r.get("url", ""))
        print(f"{r.get('folder') or '(all of public/)'}\n  {r.get('url')}\n"
              f"  expires {r.get('expires_human')}"
              f"{'  [password]' if r.get('password_set') else ''}"
              f"{chr(10) + '  WARNING: ' + bad if bad else ''}")
    # Folders without a token still exist and still have an address: showing them
    # stops "not published" from being read as "does not exist".
    unpublished = [f for f in folders() if f not in published]
    if unpublished:
        print("\nNot published — reachable only by someone logged in:")
        for f in unpublished:
            url, note = internal_url(f)
            print(f"{f}\n  {url or '(no internal address: ' + note + ')'}")


def doctor() -> dict:
    """
    What is ALIVE on this install, right now. Run this instead of trusting a config
    written months ago: fleet installs are not identical (some still have an
    always-public static host, others do not).
    """
    def get(url):
        try:
            r = urllib.request.Request(url, method="GET", headers={"User-Agent": UA})
            with urllib.request.urlopen(r, timeout=10) as resp:
                return resp.status
        except urllib.error.HTTPError as e:
            return e.code
        except Exception:
            return None

    rep = {
        "brain_root": str(ROOT),
        "infra_declared": "boot/local.yaml public:" if infra() else "NO — no public: section in boot/local.yaml",
        "install_host": instance_host() or "(unknown)",
        "share_api": ", ".join(u for u, _ in share_api_candidates()),
        "slug": slug_candidates()[0],
        "internal_route": None,
        "token_driver": None,
        "legacy_static": None,
    }

    url, note = internal_url()
    rep["internal_route"] = url or f"KO: {note}"

    res = call("list")
    rep["token_driver"] = "ok" if "published" in res else f"KO: {res.get('error')}"
    if isinstance(res.get("published"), list):
        rep["published"] = res["published"]

    legacy = str(infra().get("static_url")
                 or config().get("legacy_base_url") or config().get("base_url") or "").strip()
    if legacy:
        code = get(legacy.rstrip("/") + "/")
        rep["legacy_static"] = f"{legacy} → HTTP {code}" + ("  (ALIVE)" if code == 200 else "  (not serving)")
    return rep


def main() -> None:
    p = argparse.ArgumentParser(
        description="Resolve, publish and revoke the addresses of this brain's public/ folders.")
    p.add_argument("action", choices=["link", "list", "publish", "revoke", "doctor"])
    p.add_argument("folder", nargs="?", default="", help="folder relative to public/ (empty = all of public/)")
    p.add_argument("--days", type=int, default=30, help="lifetime in days (1-90, default 30)")
    p.add_argument("--password", default="", help="protect the page with a password")
    p.add_argument("--json", action="store_true", help="raw output")
    a = p.parse_args()

    # One place, every action that takes a folder: `publish public/x` and `publish x`
    # are the same request. Doing it per-action is how `link` ended up forgiving while
    # `publish` stayed strict, which is worse than either rule applied consistently.
    a.folder = normalize_folder(a.folder)

    if a.action == "link":
        url, note = internal_url(a.folder)
        if not url:
            sys.exit(f"No internal address available: {note}")
        print(json.dumps({"url": url, "folder": a.folder, "kind": "internal"}, indent=2)
              if a.json else url)
        return

    if a.action == "doctor":
        rep = doctor()
        print(json.dumps(rep, indent=2, ensure_ascii=False) if a.json else
              "\n".join(f"{k}: {v}" for k, v in rep.items() if k != "published"))
        return

    if a.action == "list":
        res = call("list")
        if a.json:
            res["unpublished"] = [f for f in folders()
                                  if f not in {r.get("folder") or "" for r in res.get("published", [])}]
            print(json.dumps(res, indent=2, ensure_ascii=False))
        elif "published" in res:
            show(res["published"])
        else:
            sys.exit(f"Cannot read the publications: {res.get('error')}")
        return

    if a.action == "revoke":
        if not a.folder:
            sys.exit("revoke needs a folder.")
        res = call("revoke", folder=a.folder)
        if res.get("error"):
            sys.exit(f"Revoke failed: {res['error']}{missing_folder_note(res['error'], a.folder)}")
        print(json.dumps(res, indent=2) if a.json else
              f"Revoked: {a.folder} — the link no longer answers.")
        return

    res = call("publish", folder=a.folder, days=a.days, password=a.password)
    if res.get("error") or not res.get("url"):
        err = res.get("error", "no URL returned")
        sys.exit(f"Publish failed: {err}{missing_folder_note(err, a.folder)}")
    if bad := check_url(res["url"]):
        sys.exit(f"Published, but the link is unusable: {bad}\n(raw url: {res['url']})")
    print(json.dumps(res, indent=2, ensure_ascii=False) if a.json else
          f"{res['url']}\nexpires {res['expires_human']} ({res['days']} days)"
          f"{'  [password set]' if res.get('password_set') else ''}")


if __name__ == "__main__":
    main()
