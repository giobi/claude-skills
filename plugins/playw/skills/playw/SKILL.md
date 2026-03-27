---
name: playw
description: "Playwright sidecar mode — visual verification after every change"
user-invocable: true
argument-hint: "[URL]"
requires:
  capabilities: [playwright]
---

**Playwright Sidecar** — Occhi aperti per tutta la sessione

## Cosa fa

Attiva la **modalità sidecar Playwright**: da questo momento, dopo OGNI modifica visuale (CSS, HTML, Blade, JS), fai automaticamente uno screenshot della pagina target e mostralo in chat.

## Setup

1. Parsing `$ARGUMENTS`:
   - Se è un URL → quello è il target
   - Se è un nome progetto → deduci URL dal wiki
   - Se vuoto → usa l'URL dell'ultimo progetto attivo o chiedi

2. Salva il target URL come variabile di sessione mentale. Da ora in poi:
   - Dopo ogni `Edit` su file frontend (blade, css, js, html, vue, tsx) → screenshot automatico
   - Non chiedere "vuoi che faccia screenshot?" — FALLO E BASTA
   - Se la modifica non è visuale (backend, config, API) → skip

## Come fare screenshot

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    page.goto(TARGET_URL)
    page.wait_for_timeout(2000)
    page.screenshot(path='/tmp/playw-check.png', full_page=False)
    browser.close()
```

Poi mostra lo screenshot con Read tool.

## Regole

- **Automatico**: non chiedere, non annunciare — fai lo screenshot e mostralo
- **Veloce**: viewport 1920x1080, wait 2s, no full_page (solo above the fold)
- **Commenta**: se vedi qualcosa di rotto nello screenshot, dillo subito
- **Sovrascrivere**: usa sempre `/tmp/playw-check.png` (non accumulare file)
- **Disattiva**: l'utente dice "stop playw" o "basta screenshot" → smetti

## Output attivazione

```
🎭 Playwright sidecar attivo → {URL}
Dopo ogni modifica frontend faccio screenshot automatico.
```

## Args Provided:
```
$ARGUMENTS
```
