---
name: figma
description: "Figma Parser — estrai design system da file Figma via API"
argument-hint: "[figma-url] [parse|export|pressless]"
---

# Figma Parser

**Input**: `$ARGUMENTS`

## Cosa fa

Prende un URL Figma e ne estrae il design system via API REST: colori, font, spaziature, layout, frame, componenti.

## Requisiti

- `FIGMA_ACCESS_TOKEN` nel `.env` (gratis: https://www.figma.com/developers/api#access-tokens)

## Wrapper

```python
import sys; sys.path.insert(0, '${CLAUDE_SKILL_DIR}/scripts')
from figma_parser import FigmaParser

fp = FigmaParser()  # legge FIGMA_ACCESS_TOKEN da .env
```

## Azioni

### parse (default)

```python
data = fp.parse_url(figma_url)
ds = fp.extract_design_system(data)
# → colori, font, frame, componenti, spaziature, layout grid
```

### export

```python
data = fp.parse_url(figma_url)
ds = fp.extract_design_system(data)
file_key = fp.parse_figma_url(figma_url)["file_key"]
frame_ids = [f["id"] for f in ds["frames"]]
saved = fp.download_frame_images(file_key, frame_ids, output_dir=f"storage/figma/{slug}/", format="png", scale=2)
```

### pressless

```python
data = fp.parse_url(figma_url)
pds = fp.to_pressless_design_system(data)
# → palette, typography, spacing, layout, frame inventory
# Suggerisci: "Vuoi lanciare /pressless con questo design system?"
```

## Output

```
🎨 **Figma Parser: {url}**

**Palette:** BG: {bg} | Text: {text} | Accent: {accent} ({theme} theme)
**Typography:** Heading: {heading_font} | Body: {body_font}
**Frame:** {N} frame trovati
**Componenti:** {N}

📁 Output: storage/figma/{slug}/
```

## Regole

1. **Token obbligatorio** — se `FIGMA_ACCESS_TOKEN` non c'e, spiega come ottenerlo
2. **File deve essere condiviso** — se 403, spiega che serve link pubblico
3. **Solo lettura** — non modificare nulla su Figma
4. **Asset in storage/** — mai in public/
5. **Rate limiting** — rispetta i limiti API Figma
