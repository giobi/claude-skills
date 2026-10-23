---
name: brand
description: "Generations Brand Book V02 — palette, gradients, logos, design tokens for minisites and presentations. One accent per page, dark shell canvas, sub-brand gradient rules the hero."
user-invocable: true
argument-hint: "[rpo|worktech|executive|interim|recruitment|gram|generations|palette|logos|css|reload]"
---

# /brand — Generations Design System

Source: **SharePoint /5. Marketing/BrandBook26 - Generations/Generations - Brand Guidelines - V02.pdf** (V02, July 2026). Color codes, gradient stops and type families are extracted from the official *"Palette de couleurs"* SVGs of each sub-brand — they are not estimates.

This skill replaces the old standard with the coral accent `#e8634a` (retired 2026-07). The dark canvas stays, the sub-brand gradient replaces the coral.

---

## The 7 brand families

Each sub-brand has a **primary + gradient** and — when needed — deep + shadow accents. Only one sub-brand accents a page.

| Slug | Sub-brand | Gradient (from → to) | Primary | Deep | Shadow | Use for |
|------|-----------|----------------------|---------|------|--------|-----------|
| `generations` | Generations (marque mère) | `#5bd5fc → #38bef4 → #10a5eb` | `#10a5eb` | — | `#12254f` | Multi-service pages, corporate umbrella, mother mesh |
| `recruitment` | Recruitment | `#5bd5fc → #35bdf3 → #10a5eb` | `#10a5eb` | `#2f7fc4` | `#12254f` | Permanent recruitment, sourcing, job pages |
| `rpo` | RPO Solutions | `#fca9ec → #fc7fe6 → #fc58e1` | `#fc58e1` | `#dc04b8` | `#630353` | RPO proposals, client hubs (Hedgren, CEFTA, Aqvita, Abbove), delivery portals |
| `executive` | Executive Search | `#f5c976 → #db9c30` | `#db9c30` | `#a06817` | `#35150d` | Executive/board search, confidential mandates |
| `interim` | Interim Management | `#ffad40 → #ff932e → #ff7b1c` | `#ff7b1c` | `#e05e00` | `#5d2700` | Interim / fractional / transformation |
| `worktech` | WorkTech Solutions | `#57ddc6 → #a8e046` | `#85c021` | — | `#192600` | Products (portals, agents, Sales Companion, minisites), tech demos |
| `gram` | GRAM by Generations | `#b77ae8 → #7540b8` | `#7540b8` | — | — | Psychometric reports, assessments, GRAM product |

### GRAM — 7 profiles, 7 gradients

Each GRAM archetype shares a gradient with a sub-brand (elegant, not a coincidence).

| Profile | Gradient | Shared with |
|---------|----------|---------------|
| Achiever (SA) | `#b77ae8 → #7540b8` (violet) | — GRAM signature |
| Challenger (C) | `#fca9ec → #fc58e1` | RPO |
| Sustainer (SS) | `#ff7770 → #e73542` (coral-red) | — |
| Emancipator (FS) | `#ffad40 → #ff7b1c` | Interim |
| Harmonizer (H) | `#f5c976 → #db9c30` | Executive |
| Trendsetter (CNC) | `#57ddc6 → #a8e046` | WorkTech |
| Committer (SR) | `#5bd5fc → #10a5eb` | Recruitment |

---

## Rules (hard)

1. **One sub-brand per page.** The sub-brand gradient accents the hero, the primary CTA, the card top-border, the hover glow. Other brands appear only as secondary chips/logos, never as a parallel accent.
2. **Dark shell is the default.** `#06060a` background, glass cards (`rgba(255,255,255,.03/.07/.12)`). Light shell only for official Executive PDFs and GRAM print output.
3. **The hero mesh uses 3–4 stops** of the active gradient. For the mother brand: multi-hue mesh (pink+blue+green+orange+violet) — the only exception to "one gradient per page".
4. **Typography:** Inter (headings + body), JetBrains Mono (numbers, KPIs, badges, code). Only these two.
5. **The active sub-brand is chosen via `data-brand="…"`** on `<html>` or `<body>`. A single attribute changes everything: hero, CTA, glow, section borders.
6. **Never** use coral `#e8634a` as the default accent again. Never Bootstrap/Material templates. Never a light theme without a brand rationale.

---

## How to use it in a minisite

### 1. HTML setup

```html
<!DOCTYPE html>
<html lang="en" data-brand="rpo">
<head>
  <meta charset="utf-8">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/path/to/brand/tokens.css">
</head>
<body>
  <div class="hero-mesh"></div>
  <div class="grid-overlay"></div>
  <main class="content">
    <h1>Client Hub <span class="grad">Hedgren</span></h1>
    <button class="btn btn--primary">Open pipeline</button>
    <div class="card card--accent-top">…</div>
  </main>
</body>
</html>
```

### 2. Switching sub-brand

Change only `data-brand="…"`. The custom properties `--accent`, `--accent-gradient`, glow, badge etc. follow automatically.

### 3. Available assets

```
.claude/skills/brand/
├── brand.json          # palette + machine-readable rules
├── tokens.css          # drop-in design tokens (custom properties + base components)
├── SKILL.md            # this guide
├── new_page.py         # start a page from a template (see "Templates")
├── templates/
│   └── briefing/       # long-read layout: index.html, style.css, fonts/, logos/, motifs/
└── assets/
    ├── logos/
    │   ├── generations/{color,color-h,color-it,white,white-text,white-it,bw,icon,palette}.{svg,png}
    │   ├── recruitment/…
    │   ├── rpo/…
    │   ├── executive/…
    │   ├── interim/…
    │   ├── worktech/…
    │   └── gram/…
    └── patterns/
        ├── generations--motif-{01..04}.{svg,png}
        └── gram--motif-{01,02}.{svg,png}
```

Variant naming:
- `color` — primary color version (reference)
- `color-h` — horizontal color lockup
- `color-it` — icon + text color lockup
- `white` — all white (dark backgrounds)
- `white-text` — text only, white
- `white-it` — icon + text white lockup (V2)
- `bw` — black & white (monochrome)
- `icon` — G symbol only
- `palette` — color reference sheet

---

## Templates

Ready layouts already dressed in the brand. Start a page from one of these before writing
a layout by hand: the brand rules are already applied, and the page comes out
self-contained (tokens, logo, motif and fonts sit in its own folder, so it renders the
same at the internal `/artifact/` address and behind a `/share/<token>/` link).

```bash
python3 .claude/skills/brand/new_page.py public/<folder> --brand recruitment \
  --title "Head of Partnership Management" --accent "Partnership Management" \
  --kicker "Candidate briefing"
python3 .claude/skills/brand/new_page.py --list
```

`--brand` sets `data-brand`, the logo and the hero motif; `--accent` is the trailing part
of the title drawn with the gradient (default: the last word). The script refuses to
write into a folder that already has an `index.html`.

Then replace the example content. Each block in the template is a component with a
comment saying what it is for: keep the ones the content needs, delete the rest,
renumber the sections, and keep the side index (`.toc`) in sync with the section ids.

### `briefing` — a long read handed to one person before a step

Candidate briefing before an interview, onboarding pack, client brief: someone else's
document (often a Word file) made readable, without rewriting it. First built for the
Fairtrade Belgium candidate briefing (Lorraine, October 2026).

Structure: top bar with logo and badge → hero (title, lead, two buttons, motif) → side
index + main column grouped in **parts** (`.part`) of **numbered sections**
(`section` + `.num`) → footer.

| Component | Markup | For |
|-----------|--------|-----|
| Part label | `.part` | groups sections: "Part one · The organisation" |
| Section | `section#id` + `.num` + `h2` | one numbered topic; the id feeds the side index |
| Side index | `nav.toc` with `.t-label` per part | hidden below 980px |
| Chain | `.chain` of 4 `.card` with `.ico` + `.k` | a sequence of steps, left to right |
| Card grid | `.grid2` / `.grid3` + `.card` (`.card.slim` for labels only) | a bullet list whose items have a name and an explanation |
| Dims | `.dims`, one card `.card--accent-top` + `badge--brand` | three facets, one flagged as the priority |
| Callout | `.callout` (with optional `.c-title`), `.callout.soft` | the sentence not to miss; soft = note or caveat |
| Lists | `ul.clean`, `ol.steps` (filled), `ol.steps.outline` | bullets; questions to answer; a suggested structure |
| Prep box | `.card.card--accent-top.prep` | what the reader has to bring |
| News | `article.card.news` with `.src`, `.stats`, `.read` | an external article with its figures and link |
| People | `.people` of `.card.person` (`.avatar`, `.role`, `a.li`) | who the reader will meet |

Motifs: the mother brand uses `generations--motif-01` (multi-hue, as the brand book
allows only for it); every sub-brand uses `motif-03` recoloured with its own gradient from
`brand.json`, so a page never carries a second accent.

Rules that come with it: keep the source text as written (fix typos and duplicates, say
what you changed); never fill a role, a title or a figure you have no source for — leave
it out; icons are Lucide, never emoji.

---

## Commands

```
/brand                    → show the 7 families + live palette
/brand rpo                → CSS/HTML snippet for an RPO page (accent + logo path)
/brand worktech           → CSS/HTML snippet for a WorkTech page
/brand palette            → all hex values + copy-ready gradient css
/brand logos              → logo paths for each sub-brand
/brand css                → path to tokens.css + how to include it
/brand demo               → link to the published demo minisite
/brand template [name]    → start a page from a ready layout (new_page.py, see "Templates")
/brand reload             → re-download the brand book from SharePoint
```

### Copy-ready snippet (RPO)

```css
:root { /* set at page level or use data-brand="rpo" */
  --accent:         #fc58e1;
  --accent-light:   #fca9ec;
  --accent-mid:     #fc7fe6;
  --accent-deep:    #dc04b8;
  --accent-shadow:  #630353;
  --accent-gradient: linear-gradient(135deg, #fca9ec 0%, #fc7fe6 51%, #fc58e1 99%);
}
```

### Copy-ready snippet (WorkTech)

```css
:root {
  --accent:         #85c021;
  --accent-light:   #a8e046;
  --accent-mid:     #57ddc6;
  --accent-deep:    #85c021;
  --accent-shadow:  #192600;
  --accent-gradient: linear-gradient(135deg, #57ddc6 0%, #a8e046 100%);
}
```

---

## Reload from the brand book (SharePoint)

If the brand book changes (V03, V04…), update the assets:

```bash
# 1. Download the new pack from SharePoint
python3 -c "
import sys; sys.path.insert(0, '/home/brain/data/tools/lib')
from sharepoint import SharePointClient
sp = SharePointClient()
drive = 'b!bT7EIzj7u0yucGCs_bzcLpcO3gmVOc5FnJRLWrXWXwKtL859sHD3S4MuOur8ChTh'
for z in ['01 — Generations (marque mère)', '02 — Recruitment', '03 — RPO Solutions',
          '04 — Executive Search', '05 — Interim Management', '06 — WorkTech Solutions',
          '07 — GRAM by Generations', '08 — Motifs & éléments']:
    # ... (see storage/brand-book/ for last download script)
    pass
"

# 2. Extract the palette SVGs + regenerate brand.json + tokens.css
# 3. Update the '7 families' section above if there are new sub-brands
```

Last extraction: **2026-07-29** from V02.

---

## Published demo

See all sub-brands applied live: **https://public.grworktech.com/giant/brand-demo/**

---

## Don't

- ❌ Coral `#e8634a` as default (it was a pre-brand-book placeholder, retired)
- ❌ Two sub-brands as equal accents on the same page
- ❌ Light theme without a mandate (Executive Search PDF, GRAM PDF are the only exceptions)
- ❌ Default Bootstrap/Material/Tailwind templates
- ❌ Fonts other than Inter + JetBrains Mono
- ❌ Coral `#e8634a`, Bootstrap blue `#0d6efd`, Material purple `#6200ea` — non-brand colors
- ❌ Arbitrary gradients — use only those from the brand book
