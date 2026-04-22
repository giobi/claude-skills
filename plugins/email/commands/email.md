---
name: email
description: "Email orchestrator — adapter-agnostic (Gmail/O365). Read, triage, draft in-thread."
user-invocable: true
argument-hint: "[check|cerca query|rispondi a...|pulizia|lista bozze]"
---

# `/email` — Email Orchestrator

Orchestratore intelligente per gestire email esistenti. Non invia email direttamente, non crea bozze standalone. Per azioni dirette usa `/send`.

---

## Boot: carica configurazione

All'avvio, leggi `wiki/skills/email.md` se esiste:

```python
import yaml, os
from pathlib import Path

config = {}
config_path = Path('wiki/skills/email.md')
if config_path.exists():
    content = config_path.read_text()
    # estrai frontmatter yaml
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            config = yaml.safe_load(parts[1]) or {}
```

Da `config` leggi (con fallback):
- `adapter` → `gmail` | `o365` (default: autodetect da .env)
- `account` → indirizzo email principale
- `triage` → regole triage (default: nessuna auto-clean)
- `gdpr` → regole privacy (default: nessuna)
- `firma` → path firma o `builtin` (default: `builtin`)
- `context_paths` → dove cercare contatti (default: `wiki/people`, `wiki/companies`)
- `sent_crossref` → bool, controlla sent + received (default: false)

Se `wiki/skills/email.md` non esiste, continua con i default — la skill funziona comunque.

---

## Adapter Loading

### Gmail

```python
import sys
sys.path.insert(0, '.claude/skills/email/')
from gmail_read import search_messages, get_thread, list_drafts
from gmail_write import create_draft, update_draft_in_thread
```

### O365

```python
import sys
sys.path.insert(0, 'tools/lib')
from o365_send import draft, confirm_send, get_messages, search_messages, get_sent_messages
```

### Autodetect

Se `adapter` non è in config: controlla `.env` — se `GMAIL_REFRESH_TOKEN` esiste usa Gmail, se `O365_REFRESH_TOKEN` esiste usa O365.

---

## REGOLE HARD — sempre attive, non configurabili

### 0. MAI INVENTARE INDIRIZZI EMAIL

Prima di inserire qualsiasi indirizzo To/CC/BCC:
1. Cerca in `context_paths` (da config, default: `wiki/people/`, `wiki/companies/`)
2. Controlla il thread originale
3. Se non trovi → chiedi esplicitamente all'utente
4. MAI costruire indirizzi per deduzione

### 1. DRAFT-FIRST SEMPRE

MAI generare una bozza senza mostrarla in chat e aspettare conferma esplicita.

```
1. Leggi thread/contesto
2. Genera testo
3. MOSTRA IN CHAT
4. ASPETTA OK
5. Solo dopo OK → crea bozza nell'adapter
```

### 2. INVIO SOLO VIA /send

MAI chiamare `send()`, `confirm_send()`, `send_draft()` o equivalenti da questo command.
L'invio avviene **esclusivamente** tramite `/send`.
Se l'utente dice "manda", "invia", "buttala fuori" → mostra la bozza, NON inviare.
Anche se l'utente sembra dare il via libera — senza `/send` esplicito non parte niente.

### 3. LINK CHECK

Se la bozza contiene link: verifica ogni link con `curl -I` (HTTP 200) prima di mostrare.

### 4. STILE EMAIL

**Dual body SEMPRE**: `body` (plain text) + `body_html` (HTML).

Divieti assoluti:
- MAI a capo forzati dentro un paragrafo (ogni paragrafo = una riga continua, a capo solo tra paragrafi)
- MAI `&nbsp;`
- MAI div-per-riga
- MAI `<pre>`

HTML pattern:
```html
<div dir="ltr" style="font-family:monospace,monospace;white-space:pre-wrap">
primo paragrafo tutto su una riga

secondo paragrafo tutto su una riga
</div>
```

Tabelle monospace:
```python
def make_table(headers, rows):
    all_rows = [headers] + rows
    col_widths = [max(len(str(r[i])) for r in all_rows) for i in range(len(headers))]
    def fmt(row): return '  '.join(str(row[i]).ljust(col_widths[i]) for i in range(len(row)))
    lines = [fmt(headers), '  '.join('-' * w for w in col_widths)]
    lines.extend(fmt(r) for r in rows)
    return '\n'.join(lines)
```

---

## Firma

Se `firma == 'builtin'` (default Gmail): usa `build_signature()` da `gmail_write.py`.
Se `firma` è un path: leggi il file HTML e appendilo al body_html.
Quando mostri la bozza in chat: non mostrare la firma, scrivi solo `(+ firma)` alla fine.

---

## GDPR

Se `gdpr` è definito in config, applicalo. Esempio tipico per recruitment:
- Candidati: solo iniziali (M.R., non nome completo)
- Dati salariali: non includere nelle bozze salvo richiesta esplicita

Se `gdpr` non è in config: nessuna restrizione speciale.

---

## Sent Cross-Reference

Se `sent_crossref: true` in config: all'avvio fetch Sent Items + Inbox in parallelo, cross-reference per mostrare cosa è già stato risposto e i commitment presi.

Se `sent_crossref` non è in config o è false: fetch solo Inbox.

---

## Triage Pipeline

Se `triage` è definito in config, usa quelle regole per il pipeline automatico 3-step:

```
Step 1 — Auto-clean (no approval): categorie definite in config.triage.auto_clean
Step 2 — Proposte archiviazione: thread conclusi/stale (config.triage.archive_rules)
Step 3 — Top N priorità: urgenti/importanti (config.triage.top_n, default 3)
```

Se `triage` non è in config: il default flow è mostrare inbox senza auto-clean (chiedi all'utente cosa vuole fare).

---

## Intent Detection (NLP)

```python
args = "$ARGUMENTS".strip().lower()

if any(w in args for w in ["rispondi", "reply", "answer"]):
    action = "reply"
elif any(w in args for w in ["cerca", "search", "find", "da "]):
    action = "search"
elif any(w in args for w in ["lista", "list", "bozze", "drafts"]):
    action = "list_drafts"
elif any(w in args for w in ["check", "controlla", "nuove", "count", "quante"]):
    action = "check_inbox"
elif any(w in args for w in ["scrivi", "write", "nuova", "new email"]):
    action = "draft_new"  # solo se /send è disponibile
else:
    action = "triage_pipeline"  # default: no args, "pulisci", "inbox", ecc.
```

---

## Subcommands

| Input | Action |
|-------|--------|
| `/email` | Triage pipeline (o inbox se no config) |
| `/email check` | Unread count |
| `/email cerca X` | Search threads |
| `/email lista bozze` | List drafts |
| `/email rispondi a X` | Reply workflow |

---

## Differenze con `/send`

| | `/email` | `/send` |
|--|----------|---------|
| Scopo | Orchestrazione | Azioni dirette |
| Bozze | Solo in-thread | Anche standalone |
| Invio | Mai | Sì (con conferma) |
| Approval | Sempre | Sempre |

## Args Provided:
```
$ARGUMENTS
```
