---
name: site-ripper
description: "Site Ripper — estrai design system da qualsiasi sito web via Playwright (screenshot + CSS + asset)"
argument-hint: "[url] [pagine: /,/about,/pricing]"
requires:
  capabilities: [playwright]
---

# Site Ripper

**Input**: `$ARGUMENTS`

## Cosa fa

Prende un URL qualsiasi e ne estrae il design system via Playwright: screenshot a piu breakpoint, CSS extraction, download asset (logo, favicon, hero, OG image).

## Requisiti

- `playwright` installato (`pip install playwright && playwright install chromium`)

## Wrapper

```python
import sys; sys.path.insert(0, '${CLAUDE_SKILL_DIR}/scripts')
from site_ripper import SiteRipper

ripper = SiteRipper()
```

## Uso

```python
result = ripper.rip(
    url,
    output_dir=f"storage/figma/{slug}/",
    pages=["/", "/about", "/contact"],  # pagine da visitare
    breakpoints=["desktop", "tablet", "mobile"],
)

ds = result["design_system"]
# → palette (bg, text, accent, theme)
# → typography (heading font, body font, sizes)
# → layout (header, hero, footer)
# → border_radius
# → screenshot salvati
# → asset scaricati
```

## Output

```
🔍 **Site Ripper: {url}**

**Pagine:** {N} | **Breakpoint:** desktop, tablet, mobile

**Palette:** BG: {bg} | Text: {text} | Accent: {accent} ({theme} theme)
**Typography:** Heading: {heading_font} | Body: {body_font}
**Layout:** header {si/no} | hero {si/no} | footer {si/no}
**Asset:** {N} scaricati (logo, favicon, hero...)
**Screenshot:** {N} salvati

📁 Output: storage/figma/{slug}/
```

## Regole

1. **Solo lettura** — non modificare nulla sul sito
2. **Asset in storage/** — mai in public/
3. **Rate limiting** — 1 secondo tra le pagine
4. **Playwright headless** — sempre, mai mostrare il browser
5. **Se Playwright non installato** — spiega: `pip install playwright && playwright install chromium`
