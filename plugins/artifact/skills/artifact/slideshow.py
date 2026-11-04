#!/usr/bin/env python3
"""
slideshow.py — generates a reveal.js presentation into public/<slug>/index.html,
either from an existing artifact's content or as a scaffold the agent fills in.

Why this exists: on 2026-09-15 (GR Brain workshop) a user asked for "a slideshow
from this artifact, one page" and the brain answered with a wall of text, twice.
The shared `/artifact` skill had no presentation mode at all — only static pages
built from the five artifact-1.css layouts, which are a different medium
(scrollable page) from a slideshow (fullscreen, one screen at a time). See
village TODO #1534.

Design: standalone reveal.js deck, NOT retrofitted into the artifact-1.css
layout system. Reference implementation: efesto's /talk skill
(.claude/skills/talk/talk.py, not in the fleet) — same reveal.js/CDN/Inter-font
approach, collapsed to a single file since a slideshow artifact does not need
the hub+notes+handout quartet /talk builds for an actual talk.

The reveal.js scaffold lives in shared/core/templates/minisite/slideshow.html —
edit it there to change the look of every deck generated from now on (same
"template changes here, content changes in public/" split as artifact-1.css).

Usage:
  python3 slideshow.py <slug> --title "Title" [--subtitle "..."]
                        [--from <source-slug>] [--one-page]

  <slug>            destination folder under public/ (kebab-case)
  --from            an existing public/<source-slug>/index.html to build the
                     deck FROM: its <h2> sections become slides (or, with
                     --one-page, get flattened into one dense slide). If the
                     source has no headings, or --from is omitted, a scaffold
                     is written instead and the agent fills the content by
                     editing the file — same iterative flow as /talk.
  --one-page        one fullscreen slide instead of a multi-slide deck: the
                     literal "slideshow, one page" the workshop demo needed.
  --theme           light (default) or dark. Both use this install's brand
                     (brand.py: logo, primary/secondary/accent colours, Inter):
                     light = white background, dark = the brand's dark colour
                     as background and the logo for dark backgrounds.

This script does not print a URL: rule zero of the artifact skill says the URL
is a fact you read, not one you compose — run `share.py link <slug>` after.
"""
import argparse
import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import share  # noqa: E402  (reuses ROOT / find_brain_root — same brain-location logic as /artifact)

# The branded template shipped with the skill (light/dark themes, logo, brand
# colours) wins; the old shared scaffold stays as a fallback for an install that
# still carries only that one.
OWN_TEMPLATE = Path(__file__).resolve().parent / "templates" / "slideshow" / "index.html"

THEMES = ("light", "dark")
DEFAULT_THEME = "light"

# Neutral colours used when the install has no brand configured: the deck must
# still render, readable, in both themes.
FALLBACK_PRIMARY = "#0b5fa5"
FALLBACK_SECONDARY = "#111827"
FALLBACK_ACCENT = "#38bdf8"

TEMPLATE_CANDIDATES = [
    # shared install: shared/skills/artifact/<ver>/slideshow.py -> shared/core/templates/minisite/
    Path(__file__).resolve().parents[3] / "core" / "templates" / "minisite" / "slideshow.html",
    # non-symlinked / local dev install: brain_root/.claude/skills/artifact/slideshow.py
    share.ROOT / "shared" / "core" / "templates" / "minisite" / "slideshow.html",
]

MAX_SLIDES = 10          # a deck beyond this stops being "a slideshow" for a demo
MAX_ONE_PAGE_ITEMS = 10  # bullets on the single dense slide


def template_text() -> str:
    if OWN_TEMPLATE.exists():
        return OWN_TEMPLATE.read_text(encoding="utf-8")
    for p in TEMPLATE_CANDIDATES:
        if p.exists():
            return p.read_text(encoding="utf-8")
    sys.exit(
        "Cannot find shared/core/templates/minisite/slideshow.html "
        f"(tried: {', '.join(str(p) for p in TEMPLATE_CANDIDATES)}). "
        "The template was not installed with this version of the skill."
    )


def kebab(s: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", s.lower()).strip("-")


# ---------------------------------------------------------------- extraction

class SectionExtractor(HTMLParser):
    """
    Pulls (heading, [bullet/paragraph texts]) pairs out of an artifact's
    index.html, keyed on <h2> boundaries (the artifact-1.css layouts all use
    h2 for section titles). Best-effort, not a full HTML parser: skips
    <script>/<style>, ignores markup it does not recognise, never raises on
    malformed input — a source page that doesn't parse cleanly just yields no
    sections, and the caller falls back to a scaffold.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sections = []          # [(title, [text, ...])]
        self._skip_tags = {"script", "style", "nav", "header", "footer"}
        self._skip_depth = 0
        self._in_h2 = False
        self._collect_tags = {"li", "p", "td", "dt", "dd"}
        self._in_collect = 0
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "h2":
            self._in_h2 = True
            self._buf = []
        elif tag in self._collect_tags:
            self._in_collect += 1
            self._buf = []

    def handle_endtag(self, tag):
        if tag in self._skip_tags:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag == "h2" and self._in_h2:
            title = " ".join("".join(self._buf).split())
            if title:
                self.sections.append((title, []))
            self._in_h2 = False
            self._buf = []
        elif tag in self._collect_tags and self._in_collect:
            self._in_collect -= 1
            text = " ".join("".join(self._buf).split())
            if text and self.sections:
                self.sections[-1][1].append(text)
            self._buf = []

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self._in_h2 or self._in_collect:
            self._buf.append(data)


def extract_sections(source_html: str) -> list:
    p = SectionExtractor()
    try:
        p.feed(source_html)
    except Exception:
        return []
    # keep only sections that actually have content — a bare heading is noise
    return [(t, items) for t, items in p.sections if items]


# ---------------------------------------------------------------- slide building

def esc(s: str) -> str:
    return html.escape(s, quote=False)


def slide_multi(title: str, items: list) -> str:
    # 5, not 6: a section with a long prose first bullet (an artifact's
    # opening paragraph, not something already written as short bullets)
    # already fills most of the slide — one more line and it overflows the
    # bottom. Seen on real content (grbrain, pure-food-company deck, 2026-09-16).
    lis = "\n".join(f"      <li>{esc(i)}</li>" for i in items[:5])
    return f'  <section>\n    <h2>{esc(title)}</h2>\n    <ul>\n{lis}\n    </ul>\n  </section>'


def slide_title(title: str, subtitle: str) -> str:
    # {{LOGO_TITLE}} is filled by render(): the big logo, or nothing.
    return (f'  <section class="center">\n    {{{{LOGO_TITLE}}}}\n'
            f'    <h1>{esc(title)}</h1>\n    <h3>{esc(subtitle)}</h3>\n  </section>')


def load_brand() -> dict:
    """This install's brand (brand.py). Never fatal: no brand, neutral deck."""
    try:
        import brand  # noqa: WPS433 — same folder as this script
        return brand.resolve()
    except SystemExit:
        return {}
    except Exception:
        return {}


def as_img(logo: str) -> str:
    """The logo appears twice (title slide and corner). Two inline copies of the
    same <svg> share their gradient/clip ids, and when the corner copy is hidden
    the title copy loses the shapes that point at those ids (seen on grbrain,
    2026-11-04: the figure vanished from the GR logo). An <img> with a data URI
    has its own document, so the copies cannot collide."""
    if not logo.lstrip().startswith("<svg"):
        return logo
    import base64
    data = base64.b64encode(logo.encode("utf-8")).decode("ascii")
    return f'<img src="data:image/svg+xml;base64,{data}" alt="">'


def logo_file(logo: str):
    """(filename, bytes) for a logo given as inline <svg> or <img src="data:...">,
    or None. The deck links the logo as a file next to index.html instead of
    inlining it: a GR dark logo inlined twice made a 167 KB index.html that the
    model then had to read and edit to fill the slides, and the job stalled
    (grbrain demo, 2026-11-04). With the file, index.html stays a few KB."""
    import base64
    logo = logo.strip()
    if logo.startswith("<svg"):
        return "logo.svg", logo.encode("utf-8")
    m = re.match(r'<img src="data:image/(png|jpeg|svg\+xml);base64,([^"]+)"', logo)
    if m:
        ext = {"png": "png", "jpeg": "jpg", "svg+xml": "svg"}[m.group(1)]
        return f"logo.{ext}", base64.b64decode(m.group(2))
    return None


def render(template: str, title: str, slides_html: str, theme: str, b: dict,
           logo_src: str = "") -> str:
    """Fills the template. The old shared scaffold used str.format placeholders
    ({title}, {slides_html}); the branded one uses {{UPPER}} markers, so a
    deck's own braces (CSS, JS) never need escaping."""
    if "{{SLIDES}}" not in template:
        return template.format(title=title, slides_html=slides_html)

    logo = (b.get("logo_dark_html") or b.get("logo_html") or "") if theme == "dark" else (b.get("logo_html") or "")
    logo = f'<img src="{esc(logo_src)}" alt="">' if (logo and logo_src) else as_img(logo)
    values = {
        "{{THEME}}": theme,
        "{{TITLE}}": esc(title),
        "{{PRIMARY}}": b.get("primary") or FALLBACK_PRIMARY,
        "{{SECONDARY}}": b.get("secondary") or FALLBACK_SECONDARY,
        "{{ACCENT}}": b.get("accent") or b.get("primary") or FALLBACK_ACCENT,
        "{{LOGO_ARIA_HIDDEN}}": "false" if logo else "true",
    }
    out = template
    # slides first: the title slide carries {{LOGO_TITLE}}
    out = out.replace("{{SLIDES}}", slides_html)
    out = out.replace("{{LOGO_TITLE}}", f'<div class="brand-title">{logo}</div>' if logo else "")
    out = out.replace("{{LOGO}}", logo)
    for k, v in values.items():
        out = out.replace(k, v)
    return out


def slide_placeholder() -> str:
    return '  <section>\n    <h2>[Section]</h2>\n    <ul><li>[point]</li></ul>\n  </section>'


def condense(text: str, limit: int = 65) -> str:
    """
    A one-page slide has one screen, not one paragraph per bullet. When the
    source section's first line is prose (an artifact page, not something
    already bulleted), cut it at a word boundary near `limit` chars — a
    trimmed line that still fits beats a full sentence that runs off-screen.
    """
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",.;:") + "…"


def build_deck(title: str, subtitle: str, sections: list, one_page: bool, from_slug: str) -> str:
    slides = [slide_title(title, subtitle)]

    if one_page:
        # flatten every section into one dense slide — literally "one page".
        # Text is CONDENSED, not just concatenated: a one-pager built from an
        # artifact whose sections are prose (not already short bullets) still
        # has to fit one screen. This is a trim, not a summary — if the result
        # reads choppy, edit public/<slug>/index.html by hand afterward.
        items = []
        for sec_title, texts in sections:
            items.append(f"{sec_title} — {condense(texts[0])}" if texts else sec_title)
        items = items[:MAX_ONE_PAGE_ITEMS] if items else ["[point]"]
        lis = "\n".join(f"      <li>{esc(i)}</li>" for i in items)
        note = (f'<div class="source-note">from {esc(from_slug)}</div>' if from_slug else "")
        slides.append(
            f'  <section class="dense">\n    <h2>{esc(title)}</h2>\n'
            f'    <ul>\n{lis}\n    </ul>\n    {note}\n  </section>'
        )
        return "\n\n".join(slides)

    if sections:
        for sec_title, texts in sections[:MAX_SLIDES]:
            slides.append(slide_multi(sec_title, texts))
        if len(sections) > MAX_SLIDES:
            slides.append(slide_multi(
                "More", [f"{t}" for t, _ in sections[MAX_SLIDES:MAX_SLIDES + 6]]))
    else:
        slides.append(slide_placeholder())

    return "\n\n".join(slides)


# ---------------------------------------------------------------- CLI

def cmd_new(a):
    slug = kebab(a.slug)
    if not slug:
        sys.exit("slug is empty after kebab-casing — pass a real name")
    title = a.title or slug.replace("-", " ").title()
    subtitle = a.subtitle or ""

    sections = []
    from_slug = ""
    if a.from_:
        from_slug = kebab(a.from_)
        source = share.ROOT / "public" / from_slug / "index.html"
        if not source.exists():
            sys.exit(f"--from {from_slug}: public/{from_slug}/index.html does not exist")
        sections = extract_sections(source.read_text(encoding="utf-8", errors="replace"))
        if not sections:
            print(f"NOTE: found no <h2> sections with content in public/{from_slug}/index.html "
                  "— writing a scaffold instead. Fill it in by editing the file.", file=sys.stderr)

    slides_html = build_deck(title, subtitle, sections, a.one_page, from_slug)

    d = share.ROOT / "public" / slug
    d.mkdir(parents=True, exist_ok=True)
    out = d / "index.html"
    theme = a.theme
    b = load_brand()
    raw = (b.get("logo_dark_html") or b.get("logo_html") or "") if theme == "dark" else (b.get("logo_html") or "")
    lf = logo_file(raw) if raw else None
    logo_src = ""
    if lf:
        (d / lf[0]).write_bytes(lf[1])
        logo_src = lf[0]
    out.write_text(render(template_text(), title, slides_html, theme, b, logo_src), encoding="utf-8")

    mode = "one-page" if a.one_page else "multi-slide"
    src = f" from public/{from_slug}/" if from_slug else " (scaffold, no source)"
    print(f"OK wrote public/{slug}/index.html — {mode}, {theme} theme, {len(sections) or 1} slide(s){src}")
    print(f"Get the address with: python3 share.py link {slug}")
    if not sections:
        print("Content is a placeholder — edit public/%s/index.html before handing out the link." % slug)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug", help="destination folder under public/")
    ap.add_argument("--title", default="")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--from", dest="from_", default="", help="existing public/<slug>/index.html to build slides from")
    ap.add_argument("--one-page", action="store_true", help="one fullscreen slide instead of a deck")
    ap.add_argument("--theme", choices=THEMES, default=DEFAULT_THEME,
                    help="light (white background, brand colours as text) or dark (brand dark colour as background)")
    ap.set_defaults(fn=cmd_new)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
