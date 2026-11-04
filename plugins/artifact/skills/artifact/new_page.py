#!/usr/bin/env python3
"""
new_page.py — start an artifact from one of the layouts that ship with this skill.

The layout is structure only (templates/<name>/index.html + style.css). The look —
design tokens, the logo of the sub-brand, the hero motif, the fonts — comes from the
install's brand, the same place brand.py reads: `brand.json` in
`shared/core/templates/minisite/brand/<install>/`, which points at a page kit with
its `page_kit` key. Everything is copied into the page folder, so the page is
self-contained: it renders the same at the internal /artifact/ address and behind a
/share/<token>/ link.

Usage:
    python3 new_page.py public/<folder> --title "Head of Partnership Management"
    python3 new_page.py public/<folder> --brand rpo --accent "Partnership Management" --kicker "Client brief"
    python3 new_page.py --list        # layouts, and the sub-brands this install offers

It refuses to write into a folder that already has an index.html: a template copied
over a finished page destroys it.
"""

import argparse
import datetime
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates"
sys.path.insert(0, str(HERE))
import brand  # noqa: E402  (same folder; resolves the install and its brand folder)


def load_kit():
    """The install's page kit: (kit dir, brand.json dict). Exits with the reason when
    the install has none — a layout without its tokens renders as unstyled text."""
    local = brand.load_yaml(brand.LOCAL_YAML)
    install = brand.detect_install(local)
    brand_dir = brand.BRAND_ROOT / install if install else None
    meta_path = brand_dir / "brand.json" if brand_dir else None
    if not meta_path or not meta_path.is_file():
        sys.exit(f"No brand.json for this install ({install or 'not detected'}): "
                 "these layouts need a page kit. Use the artifact-1.css layouts instead.")
    meta = json.loads(meta_path.read_text())
    kit = meta.get("page_kit")
    kit_dir = (brand_dir / kit).resolve() if kit else None
    if not kit_dir or not (kit_dir / "tokens.css").is_file():
        sys.exit(f"brand.json of '{install}' declares no usable page_kit "
                 f"(looked for tokens.css in {kit_dir}). Use the artifact-1.css layouts instead.")
    return kit_dir, meta


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", nargs="?", help="folder to create, e.g. public/fairtrade-candidate-briefing")
    ap.add_argument("--template", default="briefing")
    ap.add_argument("--brand", help="sub-brand; default: the install's default_sub (see --list)")
    ap.add_argument("--title", default="Page title", help="full title; the last word gets the gradient unless --accent is given")
    ap.add_argument("--accent", help="trailing part of the title rendered with the gradient")
    ap.add_argument("--kicker", default="Candidate briefing", help="badge text in the top bar")
    ap.add_argument("--list", action="store_true", help="list the layouts and this install's sub-brands")
    a = ap.parse_args()

    kit_dir, meta = load_kit()
    subs = meta.get("sub_brands") or {}

    if a.list:
        print("layouts:    " + ", ".join(sorted(p.name for p in TEMPLATES.iterdir() if p.is_dir())))
        print("sub-brands: " + ", ".join(f"{k} ({v})" for k, v in subs.items()))
        print("default:    " + str(meta.get("default_sub")))
        return
    if not a.target:
        ap.error("target folder is required")

    src = TEMPLATES / a.template
    if not src.is_dir():
        sys.exit(f"No layout '{a.template}'. Run --list.")
    sub = a.brand or meta.get("default_sub")
    logo = kit_dir / "logos" / f"{sub}.svg"
    if sub not in subs or not logo.is_file():
        sys.exit(f"No sub-brand '{sub}' on this install. Available: {', '.join(subs)}")

    dst = Path(a.target)
    if (dst / "index.html").exists():
        sys.exit(f"{dst}/index.html already exists: not overwriting a page. Pick another folder or remove it first.")
    dst.mkdir(parents=True, exist_ok=True)

    for name in ("index.html", "style.css"):
        shutil.copy2(src / name, dst / name)
    shutil.copy2(kit_dir / "tokens.css", dst / "tokens.css")
    shutil.copy2(logo, dst / "logo.svg")
    shutil.copy2(kit_dir / "motifs" / f"{sub}.svg", dst / "motif.svg")
    shutil.copytree(kit_dir / "fonts", dst / "fonts", dirs_exist_ok=True)

    title = a.title.strip()
    if a.accent and title.endswith(a.accent):
        plain, accent = title[: -len(a.accent)].rstrip(), a.accent
    else:
        plain, _, accent = title.rpartition(" ")

    html = (dst / "index.html").read_text()
    for key, value in {
        "{{BRAND}}": sub,
        "{{BRAND_NAME}}": subs[sub],
        "{{TITLE}}": title,
        "{{TITLE_PLAIN}}": plain,
        "{{TITLE_ACCENT}}": accent,
        "{{KICKER}}": a.kicker,
        "{{DATE}}": datetime.date.today().strftime("%B %Y"),
    }.items():
        html = html.replace(key, value)
    (dst / "index.html").write_text(html)
    print(f"{dst}/ created from '{a.template}', sub-brand {sub}. Replace the example content next, "
          f"then get the address with share.py link.")


if __name__ == "__main__":
    main()
