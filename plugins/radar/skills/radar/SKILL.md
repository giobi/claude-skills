---
name: radar
description: Radar - Collaudo siti con report ELI5 + dettagli tecnici
user-invocable: true
argument-hint: "[project|URL] [context]"
requires:
  capabilities: [web_serving, playwright]
---

**Radar** — Collaudo siti con Playwright, report client-facing

## Cosa e Radar

Evoluzione di PlayRalph. Stesso motore diagnostico Playwright, ma il report finale e **pensato per il cliente**:
- **Tab "Cosa abbiamo fatto"**: spiegazione ELI5, screenshot, linguaggio semplice
- **Tab "Dettagli tecnici"**: log, codice, errori — per il dev
- **Score 0-100**: se non e 100, ci guarda Giobi

## Infrastruttura — Multi-tenant

Radar e **multi-tenant**: ogni azienda ha il suo dominio e i suoi report separati.

### Come decidere il tenant

Il tenant si decide **SOLO dal frontmatter** di `wiki/projects/{nome}/index.md`:

1. Leggi `radar_tenant` → se presente, usa quello
2. Altrimenti leggi `company` → se corrisponde a un tenant configurato, usa quello
3. **Default: giobi** — se non c'e nessun campo che indica un altro tenant, il progetto e di Giobi

**MAI hardcodare liste di progetti per tenant.** Fa fede solo il frontmatter.

### Tenant configurati

| Tenant | URL | Report path | Git |
|--------|-----|-------------|-----|
| **giobi** (default) | `radar.giobi.com/{project}/{case}/` | `/home/web/radar.giobi.com/` | GitHub Pages (repo `giobi/radar`) |
| **netycom** | `radar.netycom.it/{project}/{case}/` | `/home/web/radar.netycom.it/` | GitHub Pages (repo `giobi/radar-netycom`) |

Dashboard di ogni tenant: `{url}/dashboard/`

### Flusso di pubblicazione

**Entrambi i tenant sono su GitHub Pages:**
1. Scrivi report + screenshot nel path locale del tenant
2. `cd {report_path} && git add -A && git commit -m "report: {project}/{case}" && git push`

## Scenari (ereditati da PlayRalph)

| Emoji | Scenario | Cosa fa | Iterazioni |
|-------|----------|---------|------------|
| fix | **Bug fix** | Issue/bug → branch → fix → verify loop | max 5 |
| search | **Bug verification** | Screenshot e documentazione del bug, niente fix | 1-2 |
| check | **Post-fix validation** | Fix gia pushato, verifico che funzioni | 1-2 |
| rocket | **Post-deploy check** | Check generale post-deploy | 1-3 |
| fire | **Crisis** | Rotto ORA, trova e fixa | max 5 |

## Regole inviolabili

1. **MAI cleanup su staging/dev** — utenti test, route, tutto resta
2. **Utenti test sono PERMANENTI** — segnati nel progetto, riutilizzati ad ogni run
3. **MAI sed/regex su file PHP/codice** — per editare codice usare script PHP, artisan, o edit tool
4. **Verifica FINALE** — l'ultimo screenshot deve essere DOPO ogni operazione

## Step 0: Parse input e carica progetto

```python
args = "$ARGUMENTS".strip()

# Detect project name vs URL
if args starts with "http":
    target_url = first_word
    project = resolve_from_domain(target_url)
else:
    parts = args.split(maxsplit=1)
    project_name = parts[0]
    context = parts[1] if len(parts) > 1 else ""
    # Carica wiki/projects/{project_name}/index.md
    # Leggi frontmatter: domain_dev, server_dev, server_dev_path, repo, github_token_env
    # Leggi sezione PlayRalph: test_user, test_password, auth_type, login_url, setup_notes
```

### Dati necessari dal progetto

Il file `wiki/projects/{nome}/index.md` DEVE avere nel frontmatter:

```yaml
server_dev: cloudways-athena.giobi.com
server_dev_path: /home/.../public_html
domain_dev: estendo.sel.re
repo: https://github.com/org/repo
github_token_env: NETYCOM_GITHUB
```

E una sezione PlayRalph nel body:

```markdown
## PlayRalph

**Utente test permanente su {domain_dev}:**
- Email: test@netycom.com
- Password: xxx
- Setup notes: "Serve store ID 18 + Spatie role Admin"
```

**Se mancano dati:** chiedi a Giobi. Non improvvisare.

## Step 1: Scenario detection + questionario interattivo

### Auto-detect

```python
context_lower = context.lower()

if any(w in context_lower for w in ["non funziona", "rotto", "errore", "500", "bug", "fix", "broken"]):
    scenario = "bugfix"
elif any(w in context_lower for w in ["verifica bug", "documenta", "screenshot del bug", "mostrami"]):
    scenario = "verification"
elif any(w in context_lower for w in ["post-fix", "ho fixato", "ho pushato", "verifica fix", "funziona ora"]):
    scenario = "postfix"
elif any(w in context_lower for w in ["deploy", "post-deploy", "dopo il deploy", "rilascio"]):
    scenario = "postdeploy"
elif any(w in context_lower for w in ["down", "crash", "urgente", "crisis", "in palla", "esploso"]):
    scenario = "crisis"
else:
    scenario = None  # → questionario
```

### Se manca contesto → questionario interattivo con AskUserQuestion

## Step 2: Esecuzione per scenario

Identico a PlayRalph (vedi `/playralph` per i dettagli di ogni scenario).

## Step 3: Auth autonoma — Entra ovunque se hai accesso

Identico a PlayRalph (vedi `/playralph` Step 3 per il dettaglio completo delle strategy).

**TL;DR dell'ordine di decisione:**

```
1. Sezione Radar nel progetto con radar_auth_cmd? → usa quello
2. Credenziali esplicite (email/password)? → form login con Playwright
3. Server + path? → auto-detect tipo app:
   - Laravel con artisan → radar:login o tinker magic link
   - WordPress con wp-cli → password temporanea
   - Altro → route temporanea o sessione DB
4. Niente accesso? → chiedi a Giobi
```

### Timeout e waitUntil
- `domcontentloaded` (non `networkidle`)
- Timeout 60s per navigazione
- `asyncio.sleep(3)` dopo ogni navigazione per Livewire/SPA

## Step 4: Analisi log

```bash
# Laravel
ssh {server_alias} "grep 'local.ERROR' {server_dev_path}/storage/logs/laravel-$(date +%Y-%m-%d).log | tail -5"

# WordPress
ssh {server_alias} "tail -20 {server_dev_path}/wp-content/debug.log"
```

## Step 5: Report finale → Radar

### Struttura report

```
/home/web/radar.giobi.com/{project}/{YYYY-MM-DD-slug}/
├── index.html          ← Report HTML self-contained
├── screenshot-1.png
├── screenshot-2.png
└── ...
```

### Report HTML — Template

Il report DEVE avere:

1. **Header**: brand Radar, titolo progetto + caso, meta (data, target, scenario, iterazioni)

2. **Score card**: cerchio SVG con score 0-100 + frase riassuntiva ELI5
   - 100 = tutto perfetto
   - 80-99 = funziona, piccole cose da migliorare
   - 50-79 = problemi significativi
   - 0-49 = rotto

3. **Cronologia intervento** (timeline): sequenza temporale con orari, pallini colorati (rosso=problema, giallo=diagnosi, verde=risolto) e durata totale.

4. **Tab "Cosa abbiamo fatto"** (DEFAULT, visibile al cliente):
   - Ogni step e una card con icona, titolo chiaro, spiegazione ELI5
   - **ELI5 FONDAMENTALE**: scrivi come se parlassi a tua nonna. Zero jargon tecnico.
     - NO: "Error 500 sulla route /contract/{id}/step/6 per config Zuora mancante"
     - SI: "Cliccando 'Paga con carta' il sito dava errore. Mancava un'impostazione."
   - Screenshot con didascalia descrittiva
   - Before/after se c'e stato un fix

5. **Tab "Dettagli tecnici"**:
   - Riepilogo: server, path, URL, scenario, iterazioni, verdict
   - Log errore (blocco dark con font mono)
   - Fix applicato (blocco dark con font mono)
   - Note tecniche

6. **Footer**: Radar - giobi.com - data generazione

### Stile

- Font: IBM Plex Mono
- Palette: stone (sfondo #fafaf9, bordi #e5e5e0, testo #1c1917)
- Card-based layout, border-radius 3px
- **Container max-width: 1080px** (non 860px — le pagine troppo strette sono illeggibili)
- Mobile-responsive
- **Template di riferimento**: `/home/web/radar.giobi.com/fasoli/2026-03-06-crisis-cartasi-xpay-fatal/index.html`

### Lingua — Regole per il tab cliente

Il tab "Cosa abbiamo fatto" e per il **cliente**, non per il dev. Regole:

- **Italiano sempre**. No inglesismi quando esiste un equivalente:
  - "plugin" → "componente" o "estensione"
  - "down" → "fuori servizio"
  - "crash" → "blocco" o "arresto"
  - "fix" → "correzione" o "risolto"
  - "bug" → "errore" o "difetto"
  - "timeline" → "cronologia"
  - "crisis" → "emergenza"
  - "root cause" → "causa"
  - "screenshot" → ok, e entrato nell'uso comune
- **Accentate**: attenzione. Rileggi prima di pubblicare. "e" senza accento dove serve "e'" e un errore grave in un report cliente.
- Il tab tecnico puo usare gergo inglese liberamente (li ha senso)

### Score 0-100 — Calcolo

```python
score = 100
deductions = {
    "error_500": -30,
    "error_404_on_key_page": -20,
    "console_errors_js": -10,
    "slow_load_over_5s": -10,
    "visual_broken": -15,
    "form_not_working": -20,
    "mobile_broken": -15,
    "ssl_issue": -25,
    "minor_visual_glitch": -5,
}
```

### Pubblicazione

```bash
cd /home/web/radar.giobi.com
git add -A
git commit -m "report: {project}/{YYYY-MM-DD-slug}"
git push
```

### Discord notifiche

```python
from discord_bot import notify

# START
report_url = f"https://radar.giobi.com/{project}/{slug}/"
notify('info', f"""Radar: {project}
Target: {url}
Scenario: {scenario}
Report: {report_url}
In corso...""", 'playralph')

# END
verdict_emoji = {"FIXED": "verde", "HEALTHY": "verde", "ISSUES": "giallo", "BROKEN": "rosso"}
notify('info', f"""Radar done: {project}
{verdict_emoji[verdict]} Score: {score}/100 — {verdict}
{report_url}
{summary}""", 'playralph')
```

### Aggiorna index progetto e dashboard

Dopo ogni report, aggiorna **due cose**:

#### 1. Project index: `{tenant_path}/{project}/index.html`
Lista dei report per quel progetto (piu recente in alto).

#### 2. Dashboard: `{tenant_path}/dashboard/index.html`
Scansiona TUTTE le directory progetto in `{tenant_path}/`, per ognuna:
- Conta i report (sottodirectory `20*`)
- Prendi l'ultimo report (data + slug)
- Estrai lo score dal report HTML
- Genera la riga nella dashboard

**Stile dashboard**: IBM Plex Mono, palette stone, layout minimal.

**IMPORTANTE**: `{tenant_path}/index.html` e una **404 elegante** — NON e la dashboard. La dashboard e SOLO su `/dashboard/`.

## Escalation

Se dopo 2 tentativi sullo stesso problema non si risolve:

```
Non riesco a risolvere in sessione.

Problemi aperti:
- [issue 1]: tentato X, Y — non risolto

Vuoi che monto un Radar in background? (max 20 iterazioni, notifica Discord)
```

## Tmux

```bash
~/.tmux/set-pane-title.sh "radar {project}"
```

## Esempi

```
/radar nexum il pagamento carta non funziona su /contract/1035/step/6
→ bugfix, login, diagnosa, fixa, report ELI5 su radar.giobi.com/nexum/

/radar nexum
→ questionario interattivo

/radar nexum verifica che il fix della tipologia step funzioni
→ postfix, screenshot, score, report

/radar https://estendo.sel.re controlla dopo il deploy
→ postdeploy, check generale, report

/radar nexum e tutto rotto
→ crisis, fix diretto, report
```

## Args Provided:
```
$ARGUMENTS
```
