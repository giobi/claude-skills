---
name: project
description: "Project-first session management — activate, create, search projects in wiki/"
user-invocable: true
argument-hint: "[nome|list|info|search|temp] [domanda]"
---

# /project — Project Manager

**Ogni sessione lavora su UN progetto.** All'avvio, l'utente dice il progetto.
Questo comando carica il contesto e attiva il progetto per la sessione.

## NLP-First

Interpreta linguaggio naturale — nessun subcommand rigido.

```
/project nexum                          → attiva nexum
/project fammi vedere tutti             → list
/project cosa sto facendo               → info
/project cerca laravel                  → search
/project cooking come faccio il riso?  → attiva + risponde
/project temp                           → usa YYYY-MM-temp
```

---

## Struttura Progetti — RAG-Oriented

**Ogni progetto è una cartella** con `index.md` obbligatorio + file separati per approfondimenti.

### Template per tipo

In `wiki/projects/.templates/`:
- `app.md` — app con codebase (backend, frontend, DB). Include Design System + Do/Don'ts UI.
- `website.md` — CMS, static site. Include domini, plugin, email.
- `business.md` — relazione cliente, preventivi, fatture.
- `personal.md` — hobby, tracking, note.

### Filosofia: Zero Token Waste

**`index.md`** = sommario esecutivo RAG-friendly (<500 token):
- Cos'è il progetto (1-2 paragrafi)
- **Mappa cartella** — cosa contiene ogni file
- Info chiave (cliente, stato, stack, contatti)
- Do/Don'ts permanenti
- Stato attuale (una riga, si SOSTITUISCE)

**File separati** = approfondimenti on-demand:
- `preventivo-xyz.md`, `tech-stack.md`, `storia-decisioni.md`
- `YYYY-MM-DD-evento.md` — eventi datati (deploy, incident, decisioni)

### Regole di Salvataggio

| Cosa | Dove va | Dove NON va |
|------|---------|-------------|
| Info strutturali (stack, accesso, domini) | `index.md` sezioni fisse | — |
| Stato attuale | `index.md` — UNA riga, si SOSTITUISCE | Non appendere timeline |
| Eventi datati (crisi, deploy, decisioni) | `diary/YYYY/` con tag progetto | NON in index.md |
| Issue tracking, changelog | `{progetto}/issues.md` o `{progetto}/log.md` | NON in index.md |
| Do/Don'ts | `index.md` — regole permanenti | NON note operative temporanee |
| Dettagli preventivi/budget | `{progetto}/preventivo-*.md` | Solo riferimento in index |

**Regola chiave:** Stato attuale = foto, non diario. Do/Don'ts = regole permanenti, non TODO.

---

## Intent Detection

```python
args = "$ARGUMENTS".strip()
args_lower = args.lower()

if args_lower == "temp":
    intent = "temp"
elif any(w in args_lower for w in ["list", "mostra", "tutti", "fammi vedere", "elenco"]):
    intent = "list"
elif any(w in args_lower for w in ["attivo", "corrente", "cosa", "status", "info"]):
    intent = "info"
elif any(w in args_lower for w in ["cerca", "trova", "search"]):
    intent = "search"
elif any(w in args_lower for w in ["analizza", "scan", "profondo"]):
    intent = "scan"
else:
    parts = args.split(maxsplit=1)
    intent = "activate"
    project_name = parts[0].lower().replace(" ", "-")
    follow_up_question = parts[1] if len(parts) > 1 else None
```

## Attivazione Progetto

```python
import glob
from pathlib import Path

project_name = "$ARGUMENTS".strip().split()[0].lower().replace(" ", "-")

# temp shortcut
if project_name == "temp":
    from datetime import datetime
    project_name = datetime.now().strftime("%Y-%m") + "-temp"

project_file = Path(f"wiki/projects/{project_name}/index.md")

# Fuzzy matching se non esiste esatto
if not project_file.exists():
    norm = lambda s: ''.join(c for c in s if c.isalnum()).lower()
    matches = [
        (p, Path(p).parent.name)
        for p in glob.glob("wiki/projects/*/index.md")
        if norm(project_name) in norm(Path(p).parent.name)
        or norm(Path(p).parent.name) in norm(project_name)
    ]
    if len(matches) == 1:
        project_file = Path(matches[0][0])
        project_name = matches[0][1]
    elif len(matches) > 1:
        # Mostra lista, chiedi di essere più specifico
        pass
```

### Output Attivazione

```
📂 **Progetto attivo: {nome}**

{primo paragrafo del progetto}

**Do:** ...
**Don'ts:** ...
**Stato attuale:** {sezione stato o "Nessuno stato precedente"}
**TODO aperti:** N
**Ultimi log:** ...

🎯 Pronto. Log e TODO di questa sessione → tag: {nome}
```

### Nuovo Progetto (se non esiste)

Intervista conversazionale:
1. Capire il tipo (App / Website / Business / Personal)
2. Domande specifiche per tipo
3. Crea `wiki/projects/{nome}/index.md` dal template giusto

## Tmux Integration (opzionale)

Se la skill `tmux` è installata, all'attivazione:

```bash
# Rinomina pane corrente
~/.tmux/set-pane-title.sh "EMOJI {nome_progetto} / {topic}"

# Rinomina window e salva mapping
CURRENT_WIN=$(tmux display-message -p '#{window_index}')
PREV=$(cat ~/.tmux/window-projects/$CURRENT_WIN 2>/dev/null || echo "")
echo "{nome_progetto}" > ~/.tmux/window-projects/$CURRENT_WIN
tmux rename-window "EMOJI {nome_progetto}"
```

Se la window era di un altro progetto → avvisa l'utente.

## Session Logger (opzionale)

Se disponibile un subagent `session-logger`, lancialo in background:

```
subagent_type: session-logger
prompt: "Sessione iniziata per progetto {nome}. Logga checkpoint ogni ~15 messaggi."
run_in_background: true
model: haiku  (o il modello più leggero disponibile)
```
