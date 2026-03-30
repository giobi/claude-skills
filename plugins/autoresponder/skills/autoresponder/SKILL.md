---
name: autoresponder
description: "AI email auto-responder — monitors inbox, drafts context-aware replies, never sends without approval"
user-invocable: false
requires:
  env:
    - AUTORESPONDER_EMAIL
    - AUTORESPONDER_NAME
    - GMAIL_ACCESS_TOKEN
    - OPENROUTER_API_KEY
  packages:
    - requests
    - python-dotenv
---

# /autoresponder — AI Email Auto-Responder

Monitora un indirizzo Gmail per thread senza risposta. Per ogni thread:
1. Cerca contesto mittente nel brain (`wiki/people/`)
2. Genera risposta AI via OpenRouter
3. Crea **bozza** Gmail — MAI invio diretto
4. (Opzionale) Notifica via Discord/Telegram
5. Estrae entità (persone, progetti) e aggiorna brain

**Filosofia:** draft-only. L'utente approva sempre prima dell'invio.

---

## Setup

### 1. Variabili .env

```bash
# Obbligatorie
AUTORESPONDER_EMAIL=yourbot@yourdomain.com    # L'indirizzo monitorato
AUTORESPONDER_NAME=AI Assistant               # Nome mittente nelle bozze
GMAIL_ACCESS_TOKEN=...                        # OAuth token Gmail
OPENROUTER_API_KEY=sk-or-...                  # Per generazione AI

# Opzionali
AUTORESPONDER_OWNER_EMAIL=you@yourdomain.com  # Tuo indirizzo personale (per escluderlo)
AUTORESPONDER_SIGNATURE=\n\n---\nAI Assistant  # Firma nelle bozze
BRAIN_URL=https://brain.yourdomain.com        # Per HTTP-Referer
DISCORD_BOT_TOKEN=...                         # Se vuoi notifiche Discord
DISCORD_DEFAULT_CHANNEL=...
```

### 2. Cron

```python
# In tools/cron/schedule.py
tasks.add(Task('autoresponder')
    .command('python3 .claude/skills/autoresponder/autoresponder.py')
    .everyMinute()
    .between('7:00', '23:00')
    .description('Check and draft replies for unreplied emails')
    .withoutOverlapping())
```

### 3. Configurazione tono (wiki/skills/autoresponder.md)

```markdown
## Tone Rules
- Known sender + tone_notes in wiki/people/: follow those notes
- Work context + unknown sender: professional, competent
- Known sender + informal relationship: casual, light humor
- Unknown sender + non-work: polite but brief
- NEVER vulgarity in email drafts
```

---

## Come funziona

### Contesto mittente

Il bot cerca `wiki/people/*.md` per il mittente (by email o nome). Se trova una entry:
- Legge `tags`, `projects`, `relationship`
- Cerca sezione "Stile Comunicazione" o "tone_notes" per calibrare il tono

Se non trova niente → tono neutro professionale.

### Generazione risposta

Passa al modello AI:
- Tutto il thread (cronologico)
- Contesto mittente dal brain
- Regole tono da `wiki/skills/autoresponder.md`
- Lingua: auto-detect dalla conversazione

### Output

- Bozza Gmail collegata al thread originale
- Log in `diary/` con mittente + azione
- Notifica Discord/Telegram (se configurato)

---

## Uso manuale

```bash
# Run normale
python3 .claude/skills/autoresponder/autoresponder.py

# Dry-run — mostra cosa farebbe senza creare bozze
python3 .claude/skills/autoresponder/autoresponder.py --dry-run
```

---

## Sicurezza

- **MAI inviare** — solo bozze. L'invio è sempre manuale.
- Salta thread dove l'ultimo messaggio è già dall'autoresponder (no loop)
- Salta newsletter, notifiche automatiche, marketing
- `AUTORESPONDER_OWNER_EMAIL` esclude tuoi messaggi dal processing
