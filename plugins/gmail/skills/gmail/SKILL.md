---
name: gmail
description: "Gmail orchestrator — triage inbox, search, draft replies in-thread"
user-invocable: true
argument-hint: "[check | cerca query | rispondi a... | pulizia | lista bozze]"
requires:
  env:
    - GMAIL_CLIENT_ID
    - GMAIL_CLIENT_SECRET
    - GMAIL_REFRESH_TOKEN
---

# /gmail — Gmail Orchestrator

Legge, fa triage e crea bozze di risposta su Gmail via OAuth. Non invia mai autonomamente.

## Setup

### 1. Google OAuth

1. Crea progetto su [Google Cloud Console](https://console.cloud.google.com)
2. Abilita **Gmail API**
3. Crea credenziali OAuth 2.0 (tipo: Desktop app)
4. Scope richiesto: `https://www.googleapis.com/auth/gmail.modify`

Aggiungi al `.env`:
```
GMAIL_CLIENT_ID=your_client_id
GMAIL_CLIENT_SECRET=your_client_secret
GMAIL_REFRESH_TOKEN=your_refresh_token
GMAIL_USER_EMAIL=you@gmail.com
```

### 2. Ottieni il Refresh Token

Usa qualsiasi OAuth flow standard con i credential sopra, oppure il file `generate-oauth-url.php` incluso nel wrapper.

## Comandi

```
/gmail                      Triage pipeline (pulizia → archiviabili → top 3)
/gmail check                Conta non letti
/gmail cerca mario rossi    Cerca thread per query
/gmail lista bozze          Lista bozze esistenti
/gmail rispondi a X         Workflow bozza risposta
```

## Default Flow: Triage Pipeline

### Step 1 — Pulizia automatica (no approval)
Cestina/archivia automaticamente newsletter, notifiche transazionali, spam.
Mostra solo conteggio: "Cestinati 4 thread (2 newsletter, 1 GitHub, 1 promo)."

### Step 2 — Proposte archiviazione
Thread conclusi o stale (risposta nostra come ultima, >7 giorni senza follow-up).
Mostra lista compatta, aspetta conferma.

### Step 3 — Top 3 Priorità
Chi aspetta risposta, deadline, urgenze. Per ognuno: **chi**, **cosa vuole**, **perché urgente**, **azione suggerita**.

## Workflow Bozza Risposta

```
1. Leggi thread completo
2. Ragiona su contenuto
3. Genera testo bozza
4. MOSTRA BOZZA IN CHAT
5. ASPETTA conferma utente
6. create_draft(thread_id=...)   ← solo bozza, NO invio
7. Restituisci draft URL
```

Invio avviene solo con comando separato esplicito.

## Logica Thread

Gmail funziona per thread, non per messaggi singoli:
- Cestinare/archiviare = azione su intero thread
- Bozze si attaccano a thread
- Mostra sempre: thread count E message count

## Regole

- **MAI inventare indirizzi email** — cerca nel database contatti, poi nel thread, poi chiedi
- **Approval-first** — mai creare bozza senza mostrare prima il testo
- **Solo in-thread** — bozze solo su thread esistenti

## Wrapper Python

```python
import sys
sys.path.insert(0, '.claude/skills/gmail')
from gmail_read import search_messages, get_thread, get_message, list_drafts
from gmail_write import create_draft, update_draft_in_thread, send_draft

# Cerca thread non letti
threads = search_messages(query="is:unread", max_results=20)

# Leggi thread completo
thread = get_thread(thread_id="1234abc")

# Crea bozza risposta
result = create_draft(
    thread_id="1234abc",
    to="user@example.com",
    subject="Re: Subject",
    body="Plain text body",
    body_html="<div>HTML body</div>"
)
```

## Intent Detection

```python
args = "$ARGUMENTS".strip().lower()

if any(w in args for w in ["rispondi", "reply"]):
    action = "reply"
elif any(w in args for w in ["cerca", "search", "find"]):
    action = "search"
elif any(w in args for w in ["lista", "bozze", "drafts"]):
    action = "list_drafts"
elif any(w in args for w in ["check", "controlla", "nuove"]):
    action = "check_inbox"
else:
    action = "triage_pipeline"  # default
```
