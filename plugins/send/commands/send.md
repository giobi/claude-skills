---
name: send
description: Direct email actions (send, standalone drafts, quick replies)
user-invocable: true
argument-hint: "[destinatario] [oggetto] [corpo] | reply thread_id [testo] | draft [dettagli]"
---

# `/send` - Direct Email Actions

**Azioni dirette veloci:** invio immediato, bozze standalone, risposte rapide senza orchestrazione.

Per gestione complessa di thread esistenti → usa `/email`

---

## Token di autorizzazione (OBBLIGATORIO)

Prima di qualsiasi chiamata a `send_draft()` o `send_message()`, crea il token:

```bash
touch /tmp/claude-send-authorized
```

Senza questo token, `gmail_write.py` blocca l'invio. Il token scade dopo 5 minuti.
Solo `/send` può creare questo token — nessun altro command è autorizzato.

---

## Workflow `/send`

```
1. Parse richiesta (send/draft/reply)
2. Genera testo
3. MOSTRA IN CHAT (formatted)
4. ASPETTA OK USER (con AskUserQuestion)
5. Solo dopo OK:
   - Send → send_message()
   - Draft standalone → create_draft() (no thread_id)
   - Reply → reply_to_message() + send/draft
6. Return conferma/URL
7. Auto-checkpoint (/save) — log email inviata, update progetto, git commit+push
```

---

## REGOLE CRITICHE

### 0. GATE: SOLO VIA `/send` COMMAND
**Email si inviano SOLO quando l'utente lancia esplicitamente il command `/send`.**

L'agente NON DEVE MAI inviare email in nessun altro contesto. Anche se l'utente dice "manda", "invia", "spedisci", "MANDA CAZZO" — senza il command `/send` l'agente puo SOLO:
- Mostrare la bozza in chat
- Chiedere se vuole procedere con `/send`

**Perche:** Un'email sbagliata inviata non si riprende. Il command `/send` e il grilletto — nient'altro.

### 1. SEMPRE APPROVAL-FIRST
Anche dentro `/send`, **MAI** inviare o creare draft senza mostrare prima il testo e ottenere conferma.

### 1b. LINK CHECK OBBLIGATORIO
Se l'email contiene **link** (URL portale, budget, report, qualsiasi cosa): **PRIMA di mostrare la bozza**, verifica ogni link con `curl -I` (HTTP 200) e se e un portale/app fai Playwright check del contenuto visibile. Un link rotto o con dati sbagliati in una mail cliente e imperdonabile.

**Formato in chat:**
```markdown
**Email da inviare**

---
**A:** destinatario@example.com
**Oggetto:** Nuovo progetto
**Azione:** Invio diretto

---

Ciao [nome],

[corpo email]

g/
[firma completa]

---

Invio questa email? (usa AskUserQuestion)
```

### 2. SEND EXISTING DRAFT (da /email)
Se l'utente ha appena creato una bozza con `/email` e poi dice "invia" o usa `/send`:

**SEMPRE** usare `send_draft(draft_id)` — MAI creare un nuovo `send_message()` duplicato.

```python
from gmail_write import send_draft

# La bozza esiste gia nel contesto della conversazione
result = send_draft(draft_id)  # invia e rimuove la bozza
```

**Come riconoscere il pattern:**
- C'e un draft_id nella conversazione recente (creato da `/email`)
- L'utente dice "invia", "manda", "send", "spedisci" riferendosi a quella bozza
- NON fornisce nuovi destinatari/oggetto/corpo → sta parlando della bozza esistente

### 3. STILE EMAIL: testo pulito (OBBLIGATORIO)

**PRIMA di scrivere qualsiasi bozza**, consulta `/ghostwriter` per stile e tono.

**Dual body SEMPRE**: `body` (plain) + `body_html` (HTML).

Regole di formattazione complete in `/email` regola 3. Riassunto:

- **MAI a capo forzati** dentro un paragrafo — ogni paragrafo e UNA riga continua, MAI wrap a 60/72/80 colonne
- **MAI `&nbsp;`** — in nessun contesto
- **MAI div-per-riga** — un container unico con `white-space:pre-wrap`
- **MAI `<pre>`** — Gmail lo renderizza male

```python
# Genera body_html da body_plain
import html
escaped = html.escape(body_plain)
body_html = f'<div dir="ltr" style="font-family:monospace,monospace;white-space:pre-wrap">\n{escaped}\n</div>'

send_message(to=to, subject=subject, body=body_plain, body_html=body_html)
```

### 4. FIRMA GIOBI (usa SEMPRE in chiusura email)

**OGNI email DEVE chiudersi con `g/` + firma completa.** Mai "Giovanni", mai "Cordiali saluti", mai "Giobi". Solo `g/`.

**Usa la funzione centralizzata `build_signature()` da `gmail_write.py`** — MAI hardcodare la firma.

```python
from gmail_write import build_signature, wrap_body_with_signature

# Metodo 1: wrap completo (body + firma)
body_html_final, body_plain_final = wrap_body_with_signature(
    body_plain=corpo_plain,
    body_html=corpo_html,
    channel='cmd',    # /send command = 'cmd'
    ai_score=30       # 0 = full AI, 100 = full human
)

# Metodo 2: solo firma (se serve controllo manuale)
sig_html, sig_plain = build_signature(channel='cmd', ai_score=30)
```

**Tag formato: `{channel}/{ai_score}`** — il channel identifica il processo, lo score il livello di intervento umano.

| Channel | Processo |
|---------|----------|
| `cmd` | `/send` — Giobi in sessione |
| `eml` | email-agent / email-followup-agent |
| `sig` | Signal-triggered action |
| `aex` | autonomous_executor |
| `chk` | email-checker |
| `dig` | daily-digest |

| Score | Significato |
|-------|-------------|
| **0** | Testo generato interamente da AI, zero input specifico |
| **10** | AI genera su indicazioni generiche dell'utente |
| **30** | AI genera con istruzioni dettagliate dell'utente |
| **50** | Utente detta il concetto, AI struttura e scrive |
| **70** | Utente modifica/corregge sostanzialmente la bozza AI |
| **85** | Utente scrive, AI corregge/formatta |
| **100** | Scritto interamente a mano |

Lo score va inserito direttamente nella bozza. Se l'utente non e d'accordo, lo corregge.

### 5. Differenza con `/email`
| Azione | `/send` | `/email` |
|--------|---------|----------|
| Invio diretto | Si | No |
| Bozze standalone | Si | No (solo in-thread) |
| Lettura thread | Opzionale | Sempre |
| Orchestrazione | No | Si |
| Invia bozza esistente | via send_draft() | No |

**Quando usare `/send`:**
- Invio veloce senza analisi complessa
- Nuova email (no thread esistente)
- Azione one-shot senza contesto
- **Inviare una bozza creata da `/email`**

---

## Wrapper Functions

### Import Pattern (adapter-agnostic)
```python
import sys
sys.path.insert(0, '.claude/skills/email')
from adapter import EmailAdapter

mail = EmailAdapter()  # auto-detect Gmail o O365
```

### Key Functions

#### **send()**
```python
result = mail.send(
    to="destinatario@example.com",
    subject="Oggetto",
    body="Corpo email...",
    confirm="SEND"
)
```

#### **draft() - Standalone**
```python
draft = mail.draft(
    to="nuovo@cliente.com",
    subject="Preventivo",
    body="Testo...",
)
```

#### **reply() - Quick Reply**
```python
result = mail.reply(
    thread_id="abc123",
    body="Perfetto, grazie!",
    send_immediately=True,  # o False per draft
    confirm="SEND"          # richiesto se send_immediately=True
)
```

---

## Intent Detection (NLP)

```python
args = "$ARGUMENTS".strip().lower()

if any(word in args for word in ["manda", "invia", "send", "spedisci"]):
    action = "send"
    send_immediately = True
elif any(word in args for word in ["bozza", "draft", "prepara"]):
    action = "draft"
    send_immediately = False
elif any(word in args for word in ["rispondi", "reply"]):
    action = "reply"
    send_immediately = any(w in args for w in ["subito", "immediatamente", "ora", "now"])
else:
    action = "draft"
    send_immediately = False
```

---

## Auto-Checkpoint (post-invio)

Dopo ogni email inviata con successo, esegui automaticamente un checkpoint `/save`:

1. **Diary log**: logga l'email inviata (destinatario, oggetto, contesto) in `diary/YYYY/`
2. **Update progetto**: se c'e un progetto attivo, appendi stato in `wiki/projects/{project}/index.md`
3. **Update entita**: se l'email riguarda persone/aziende note, aggiorna `last_contact`
4. **Git commit + push**: `git add -A && git commit -m "Email sent: {subject}" && git push`

Questo e **automatico** — non chiedere conferma per il checkpoint, fa parte del flusso /send.

---

## Args Provided:
```
$ARGUMENTS
```
