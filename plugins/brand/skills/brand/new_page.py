#!/usr/bin/env python3
"""
new_page.py — start an artifact from one of the Generations templates.

Copies templates/<template>/ into the target folder, adds the brand tokens.css, the
logo of the chosen sub-brand (viewBox already cropped to the artwork, so it renders at
its real size) and the hero motif in that sub-brand's gradient, then fills the few
placeholders of the template. The page is then self-contained: no file outside its
folder, so it renders the same under the internal /artifact/ address and under a
/share/<token>/ link.

Usage:
    python3 new_page.py public/<folder> --brand recruitment --title "Head of Partnership Management"
    python3 new_page.py public/<folder> --brand rpo --accent "Partnership Management" --kicker "Client brief"
    python3 new_page.py --list

It refuses to write into a folder that already has an index.html: a template copied
over a finished page destroys it.
"""

import argparse
import datetime
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates"

BRAND_NAMES = {
    "generations": "Generations",
    "recruitment": "Generations Recruitment",
    "rpo": "Generations RPO Solutions",
    "executive": "Generations Executive Search",
    "interim": "Generations Interim Management",
    "worktech": "Generations WorkTech Solutions",
    "gram": "GRAM by Generations",
}


def available(path, pattern="*"):
    return ", ".join(sorted(p.stem for p in path.glob(pattern)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", nargs="?", help="folder to create, e.g. public/fairtrade-candidate-briefing")
    ap.add_argument("--template", default="briefing")
    ap.add_argument("--brand", default="recruitment", help="sub-brand: " + ", ".join(BRAND_NAMES))
    ap.add_argument("--title", default="Page title", help="full title; the last word gets the gradient unless --accent is given")
    ap.add_argument("--accent", help="trailing part of the title rendered with the gradient")
    ap.add_argument("--kicker", default="Candidate briefing", help="badge text in the top bar")
    ap.add_argument("--list", action="store_true", help="list the available templates")
    a = ap.parse_args()

    if a.list:
        print(available(TEMPLATES))
        return
    if not a.target:
        ap.error("target folder is required")

    src = TEMPLATES / a.template
    if not src.is_dir():
        sys.exit(f"No template '{a.template}'. Available: {available(TEMPLATES)}")
    logo = src / "logos" / f"{a.brand}.svg"
    if a.brand not in BRAND_NAMES or not logo.is_file():
        sys.exit(f"No sub-brand '{a.brand}'. Available: {available(src / 'logos', '*.svg')}")

    dst = Path(a.target)
    if (dst / "index.html").exists():
        sys.exit(f"{dst}/index.html already exists: not overwriting a page. Pick another folder or remove it first.")
    dst.mkdir(parents=True, exist_ok=True)

    for name in ("index.html", "style.css"):
        shutil.copy2(src / name, dst / name)
    shutil.copy2(HERE / "tokens.css", dst / "tokens.css")
    shutil.copy2(logo, dst / "logo.svg")
    shutil.copy2(src / "motifs" / f"{a.brand}.svg", dst / "motif.svg")
    shutil.copytree(src / "fonts", dst / "fonts", dirs_exist_ok=True)

    title = a.title.strip()
    if a.accent and title.endswith(a.accent):
        plain, accent = title[: -len(a.accent)].rstrip(), a.accent
    else:
        plain, _, accent = title.rpartition(" ")

    html = (dst / "index.html").read_text()
    for key, value in {
        "{{BRAND}}": a.brand,
        "{{BRAND_NAME}}": BRAND_NAMES[a.brand],
        "{{TITLE}}": title,
        "{{TITLE_PLAIN}}": plain,
        "{{TITLE_ACCENT}}": accent,
        "{{KICKER}}": a.kicker,
        "{{DATE}}": datetime.date.today().strftime("%B %Y"),
    }.items():
        html = html.replace(key, value)
    (dst / "index.html").write_text(html)
    print(f"{dst}/ created from '{a.template}', sub-brand {a.brand}. Replace the example content next.")


if __name__ == "__main__":
    main()
