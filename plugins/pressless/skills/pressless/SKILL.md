---
name: pressless
description: "PressLess — AI static site generator. Crea siti statici da design di riferimento. Usa /figma e /site-ripper per estrarre design system."
argument-hint: "[domain] [url-riferimento...] [mood]"
disable-model-invocation: true
requires:
  capabilities: [playwright]
---

# PressLess — Static Site Generator

**Input**: `$ARGUMENTS`

## Cosa fa

Genera siti statici belli e performanti analizzando design di riferimento e creando 3 varianti. Usa le skill `/figma` e `/site-ripper` per estrarre i design system.

## Workflow

### 1. Input

Servono:
- **Domain/progetto** — per naming cartelle/repo
- **Riferimenti** — URL Figma, URL siti web, o descrizione mood
- **Mood** — "professional minimalist", "playful modern", "elegant corporate"

### 2. Design Extraction

In base al tipo di riferimento:

- **URL Figma** → invoca `/figma {url} pressless`
- **URL sito web** → invoca `/site-ripper {url}`
- **Solo mood** → usa design system predefinito (vedi sotto)

### 3. Output Mode

Determina dove mettere il sito:

```python
from pathlib import Path
import os

has_public = Path("public/").is_dir() and os.access("public/", os.W_OK)
has_github = bool(os.getenv("GITHUB_TOKEN"))
```

- Se `public/` disponibile → `public/pressless/{slug}/`
- Se GitHub disponibile → repo `pressless-{slug}`, 3 branch
- Se entrambi → chiedi all'utente
- Se nessuno → spiega le opzioni

### 4. Variant Generation

Genera esattamente **3 varianti HTML/CSS**:
- Semantic HTML5 (header, nav, main, section, article, footer)
- CSS moderno (Grid, Flexbox, custom properties)
- Responsive mobile-first
- Codice pulito e commentato

**Output public/:**
```
public/pressless/{slug}/
├── variant-1/index.html
├── variant-2/index.html
├── variant-3/index.html
└── assets/
```

**Output GitHub:**
```
Repository: pressless-{slug}
├── branch: variant-1 → GitHub Pages URL
├── branch: variant-2 → GitHub Pages URL
└── branch: variant-3 → GitHub Pages URL
```

## Design System predefiniti

**Font Combinations:**
1. Serif Elegant: Crimson Pro + Work Sans
2. Serif Luxury: Playfair Display + Source Sans 3
3. Sans Modern: Space Grotesk + Public Sans
4. Sans Friendly: Syne + Quicksand
5. Sans Bold: Unbounded + Karla
6. Mono Tech: JetBrains Mono + Nunito

**Color Palettes:**
1. Deep Ocean: #0a1628 bg, #e8f0ff text, #00d9ff accent
2. Industrial Mono: #0f0f0f bg, #f0f0f0 text, #ffd700 accent
3. Cyber Neon: #0d0221 bg, #f0e7ff text, #00ff88 + #ff00ff accent

**Grid Layouts:**
1. Asymmetric Hero (40/60 split)
2. Masonry Cards (auto-fit, variable heights)
3. Sidebar Inverse (240px left)
4. Swiss Grid, Magazine Layout, Diagonal Split

## Management Mode (siti esistenti)

Quando aggiorni un sito PressLess esistente:
1. Detecta se in `public/pressless/` o su GitHub
2. Analizza struttura, design system, contenuti
3. Applica modifiche (content, design, nuove pagine)
4. Mantieni consistenza con il design esistente

## Regole

1. **NEVER use emoji** nel codice HTML generato — ALWAYS inline SVG per icone
2. **No CDN per icone** — no Font Awesome, no Material Icons, solo SVG inline
3. **Asset in storage/** durante l'estrazione, in `assets/` nel sito finale
4. **HTML self-contained** — CSS inline, Google Fonts via CDN OK
5. **Nomi kebab-case** minuscolo
6. **File principale = index.html**
7. **Cross-browser** — modern browsers, graceful degradation
8. **Performance** — lazy-load images, CSS efficiente

## Esempi

```
/pressless mio-sito https://example.com https://altro.com mood: minimal dark
/pressless portfolio figma:https://figma.com/design/ABC123/My-Design
/pressless landing-page mood: playful modern, colori caldi
```
