---
name: sessions
description: Session browser — last N sessions and recently active projects from brain diary
user-invocable: true
argument-hint: "[N] | sessions | projects | <project-name>"
version: "1.0.0"
category: brain
tags:
  - sessions
  - projects
  - diary
  - brain
---

/sessions — Ultime sessioni e progetti attivi

Mostra una panoramica intelligente delle ultime sessioni di lavoro e dei progetti recenti.
Esclude automaticamente sessioni generate da cron/automazioni.

## Argomenti

$ARGUMENTS

(vuoto = default: 20 sessioni + 20 progetti | `sessions` = solo sessioni | `projects` = solo progetti | numero = cambia il limite)

## Implementazione

Esegui questo script Python:

```python
import os, sys, yaml, re
from datetime import datetime
from collections import defaultdict

BRAIN_ROOT = '/home/giobi/brain'
DIARY_YEARS = ['2026', '2025']  # anni da scandire, più recente prima

# Pattern cron da escludere (filenames)
CRON_FILENAME_PATTERNS = [
    '-worker-log', '-dbauto-log', '-night-analysis-log',
    '-rem-phase-log', '-carbon-log', '-raindrop-reading-log',
    '-night-shift-', '-daily-owl-', 'email-followup-scan',
    '-08-00-worker', '-dream-log', '-rem-phase',
]

# Tag cron da escludere
CRON_TAGS = {'autonomous', 'worker', 'dbauto', 'night-analysis', 'rem-phase',
             'carbon', 'raindrop-reading', 'night-shift', 'daily-owl', 'dream'}

# File speciali da escludere
EXCLUDED_FILES = {'2026-quotes.md', '2025-quotes.md'}

# Parse argomenti
args = "$ARGUMENTS".strip().lower()
limit = 20
show_sessions = True
show_projects = True

if args.isdigit():
    limit = int(args)
elif args == 'sessions':
    show_projects = False
elif args == 'projects':
    show_sessions = False
elif args:
    try:
        limit = int(args.split()[0])
    except:
        pass

def parse_frontmatter(content):
    m = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except:
        return {}

def is_cron_session(filename, meta):
    """Ritorna True se la sessione è stata generata da cron/automazione."""
    # Check filename
    if any(p in filename for p in CRON_FILENAME_PATTERNS):
        return True
    tags = set(meta.get('tags', []))
    cw = str(meta.get('created_with', ''))
    # Check tags cron
    if tags & CRON_TAGS:
        return True
    # I log con created_with vuoto o noto come cron sono automatici
    if meta.get('type') == 'log' and cw in ('', 'night-shift', 'daily-owl', 'worker', 'dbauto'):
        return True
    return False

def normalize_projects(raw):
    """Normalizza projects/project field in lista."""
    if not raw:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(p) for p in raw if p]
    return []

# Raccogli tutte le sessioni umane
all_sessions = []

for year in DIARY_YEARS:
    diary_dir = os.path.join(BRAIN_ROOT, 'diary', year)
    if not os.path.exists(diary_dir):
        continue
    for f in sorted(os.listdir(diary_dir), reverse=True):
        if not f.endswith('.md') or f in EXCLUDED_FILES:
            continue
        path = os.path.join(diary_dir, f)
        try:
            with open(path) as fp:
                content = fp.read()
        except:
            continue
        meta = parse_frontmatter(content)
        if not meta:
            continue
        if is_cron_session(f, meta):
            continue
        date_str = str(meta.get('date', ''))
        if not date_str:
            # estrai dalla filename
            dm = re.match(r'^(\d{4}-\d{2}-\d{2})', f)
            date_str = dm.group(1) if dm else ''
        projects = normalize_projects(meta.get('projects') or meta.get('project'))
        cw = str(meta.get('created_with', 'unknown'))
        # Determina label sessione
        is_daily = bool(cw == 'diary-merge' and re.match(r'^\d{4}-\d{2}-\d{2}\.md$', f))
        all_sessions.append({
            'file': f,
            'date': date_str,
            'projects': projects,
            'cw': cw,
            'is_daily': is_daily,
            'type': meta.get('type', ''),
        })

# Deduplication: se lo stesso giorno ha sia diary-merge che log manuali,
# teniamo entrambi ma prioritizziamo diary-merge
all_sessions.sort(key=lambda x: (x['date'], x['is_daily']), reverse=True)

# Build project → last_date map
project_last_seen = defaultdict(str)
project_session_count = defaultdict(int)

for s in all_sessions:
    for p in s['projects']:
        if s['date'] > project_last_seen[p]:
            project_last_seen[p] = s['date']
        project_session_count[p] += 1

# Output
output_lines = []

# === SESSIONI ===
if show_sessions:
    output_lines.append("## Sessioni recenti\n")
    shown = 0
    for s in all_sessions:
        if shown >= limit:
            break
        date = s['date'] or '?'
        projects = s['projects']
        if s['is_daily']:
            # Sessione giornaliera: mostra tutti i progetti
            proj_str = ', '.join(projects) if projects else '—'
            output_lines.append(f"**{date}** — {proj_str}")
        else:
            # Log manuale: mostra con slug del file
            slug = re.sub(r'^\d{4}-\d{2}-\d{2}-?', '', s['file']).replace('-log.md', '').replace('.md', '')
            proj_str = ', '.join(projects) if projects else '—'
            output_lines.append(f"  {date} ↳ {slug[:50]} ({proj_str})")
        shown += 1
    output_lines.append("")

# === PROGETTI ===
if show_projects:
    output_lines.append("## Ultimi progetti attivi\n")
    # Ordina per data ultima attività
    sorted_projects = sorted(
        project_last_seen.items(),
        key=lambda x: x[1],
        reverse=True
    )
    for i, (proj, last_date) in enumerate(sorted_projects[:limit]):
        sessions_n = project_session_count[proj]
        # Badge attività
        try:
            days_ago = (datetime.now() - datetime.strptime(last_date, '%Y-%m-%d')).days
            if days_ago == 0:
                badge = "🟢 oggi"
            elif days_ago <= 2:
                badge = f"🟢 {days_ago}g fa"
            elif days_ago <= 7:
                badge = f"🟡 {days_ago}g fa"
            elif days_ago <= 30:
                badge = f"🟠 {days_ago}g fa"
            else:
                badge = f"⚫ {last_date}"
        except:
            badge = last_date
        output_lines.append(f"{i+1:2}. **{proj}** — {badge} ({sessions_n} sessioni)")
    output_lines.append("")

print('\n'.join(output_lines))
```

Esegui lo script e mostra l'output direttamente in chat, senza wrapping aggiuntivo.

Se l'utente chiede `/resume abchat` o un nome progetto, filtra le sessioni mostrando solo quelle che toccano quel progetto.
