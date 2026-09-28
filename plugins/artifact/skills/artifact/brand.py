#!/usr/bin/env python3
"""
brand.py — resolves the brand identity (logo, accent colour, font) an artifact's
`.page-header` should carry on THIS install, and fills it into a page.

Why this exists: `/artifact` used to ship a `.page-header` that was text-only —
no logo, ever. Every install (grbrain, avocado, emibrain, and any brain-level
override) needs its own identity in that header, and it has to survive without
per-page guesswork: the same base.html works on every install, brand.py is what
tells it which logo and colour belong here.

Resolution order (first one that has a logo wins):
  1. `artifact.brand` in THIS brain's `boot/local.yaml` — an explicit override
     for a single brain that wants to diverge from its install's default.
  2. The install's own default: derived from `public.base_url` in the same
     `boot/local.yaml` (grbrain.com → grbrain, *.abchat.it / avocado → avocado,
     *emibrain* → emibrain), then loaded from
     `shared/core/templates/minisite/brand/<install>/brand.json`.
  3. Nothing configured → resolve() returns an EMPTY brand (no logo, no accent
     override). The header still renders — as a plain text brand line, exactly
     what it was before — because a page must never crash for lack of a logo.

Never invents an install name that has no brand.json: falling back to nothing is
correct, guessing a name that happens to look right is not (same rule zero as
the rest of this skill's tooling).

Usage:
    python3 brand.py resolve [--json]        # what this install/brain resolves to
    python3 brand.py fill <path/to/page.html>  # inject BRAND_* placeholders in place
"""

import base64
import json
import os
import re
import sys
from pathlib import Path


def find_brain_root() -> Path:
    def looks_like_brain(p: Path) -> bool:
        return (p / "boot").is_dir() or (p / "CLAUDE.md").is_file()

    declared = os.getenv("BRAIN_ROOT", "").strip()
    if declared and looks_like_brain(Path(declared)):
        return Path(declared).resolve()

    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if looks_like_brain(candidate):
            return candidate

    here = Path(__file__).resolve()
    if len(here.parents) > 3 and looks_like_brain(here.parents[3]):
        return here.parents[3]

    sys.exit("Cannot locate the brain root: no BRAIN_ROOT, and cwd is not inside a brain.")


ROOT = find_brain_root()
LOCAL_YAML = ROOT / "boot" / "local.yaml"

# The shared brand folder: same "shared" mount every brain on an install has
# read access to (it is where this very script lives, symlinked as
# .claude/skills/artifact/current). Walk up from this file instead of assuming
# ROOT/shared, since ROOT is the BRAIN root and "shared" is a sibling mount,
# not a subfolder of it.
def find_shared_root() -> Path:
    here = Path(__file__).resolve()
    for p in here.parents:
        if (p / "core" / "templates" / "minisite").is_dir():
            return p
        if p.name == "shared" and (p / "core").is_dir():
            return p
    # fallback: brain-relative "shared" symlink, if the install mounts it there
    guess = ROOT / "shared"
    if (guess / "core" / "templates" / "minisite").is_dir():
        return guess
    sys.exit("Cannot locate the shared brand folder (core/templates/minisite).")


SHARED = find_shared_root()
BRAND_ROOT = SHARED / "core" / "templates" / "minisite" / "brand"

INSTALL_MAP = (
    ("grbrain.com", "grbrain"),
    ("abchat.it", "avocado"),
    ("avocado", "avocado"),
    ("emibrain", "emibrain"),
)


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8", errors="replace")) or {}
    except Exception:
        return {}


def detect_install(local: dict) -> str:
    base_url = str((local.get("public") or {}).get("base_url") or "").strip().lower()
    for needle, install in INSTALL_MAP:
        if needle in base_url:
            return install
    return ""


def read_logo(brand_dir: Path, filename: str) -> str:
    """Returns ready-to-embed HTML for the logo: inline <svg> for .svg, an <img
    data:> for anything else. Inlining beats linking to a URL: it works no
    matter how (or whether) this install serves static assets out of the shared
    folder, and it survives the page being copied anywhere."""
    path = brand_dir / filename
    if not path.exists():
        return ""
    if path.suffix.lower() == ".svg":
        svg = path.read_text(encoding="utf-8", errors="replace")
        svg = re.sub(r"<\?xml[^>]*\?>\s*", "", svg)
        return svg
    data = path.read_bytes()
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    b64 = base64.b64encode(data).decode("ascii")
    return f'<img src="data:{mime};base64,{b64}" alt="">'


def resolve() -> dict:
    local = load_yaml(LOCAL_YAML)
    override = (local.get("artifact") or {}).get("brand") or {}

    install = detect_install(local)
    brand_dir = BRAND_ROOT / install if install else None
    brand_json = load_yaml(brand_dir / "brand.json") if brand_dir and (brand_dir / "brand.json").exists() else {}
    # brand.json is JSON, not YAML, but yaml.safe_load parses plain JSON fine
    # (JSON is a YAML subset) — no separate parser needed.

    name = str(override.get("name") or brand_json.get("name") or "")
    primary = str(override.get("primary") or brand_json.get("primary") or "")
    font = str(override.get("font") or brand_json.get("font") or "")

    logo_html = ""
    logo_override = str(override.get("logo") or "").strip()
    if logo_override:
        p = (ROOT / logo_override) if not logo_override.startswith("/") else Path(logo_override)
        if p.exists():
            logo_html = read_logo(p.parent, p.name)
    elif brand_dir and brand_json.get("logo"):
        logo_html = read_logo(brand_dir, brand_json["logo"])

    return {
        "install": install or "(none detected — no public.base_url match)",
        "name": name,
        "primary": primary,
        "font": font,
        "logo_html": logo_html,
        "has_brand": bool(logo_html),
    }


def fill(path: Path) -> None:
    if not path.exists():
        sys.exit(f"{path}: no such file")
    b = resolve()
    html = path.read_text(encoding="utf-8")
    html = html.replace("{{BRAND_LOGO_INLINE}}", b["logo_html"])
    html = html.replace("{{BRAND_LOGO_ARIA_HIDDEN}}", "false" if b["has_brand"] else "true")
    html = html.replace("{{BRAND_PRIMARY}}", b["primary"] or "inherit")
    path.write_text(html, encoding="utf-8")
    if b["has_brand"]:
        print(f"Brand filled: {b['name'] or b['install']} ({b['install']}) → {path}")
    else:
        print(f"No brand configured for this install ({b['install']}) — "
              f"header left without a logo, plain text only, in {path}")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("resolve", "fill"):
        sys.exit(__doc__)
    action = sys.argv[1]
    if action == "resolve":
        b = resolve()
        if "--json" in sys.argv:
            out = dict(b)
            out["logo_html"] = bool(out["logo_html"]) and f"({len(b['logo_html'])} chars)"
            print(json.dumps(out, indent=2, ensure_ascii=False))
        else:
            print(f"install: {b['install']}")
            print(f"name:    {b['name'] or '(none)'}")
            print(f"primary: {b['primary'] or '(none)'}")
            print(f"font:    {b['font'] or '(none)'}")
            print(f"logo:    {'yes, ' + str(len(b['logo_html'])) + ' chars' if b['logo_html'] else 'no'}")
        return
    if action == "fill":
        if len(sys.argv) < 3:
            sys.exit("fill needs a path: brand.py fill public/<slug>/index.html")
        fill(Path(sys.argv[2]))
        return


if __name__ == "__main__":
    main()
