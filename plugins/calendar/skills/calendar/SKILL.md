---
name: calendar
description: "Google Calendar — create, list, update, delete events"
user-invocable: true
argument-hint: "[lista | oggi | settimana | crea | modifica | cancella] [dettagli]"
requires:
  env:
    - GCAL_CLIENT_ID
    - GCAL_CLIENT_SECRET
    - GCAL_REFRESH_TOKEN
  packages:
    - requests
---

# /calendar — Google Calendar

Gestisci eventi Google Calendar in linguaggio naturale.

## Setup

```
GCAL_CLIENT_ID=...
GCAL_CLIENT_SECRET=...
GCAL_REFRESH_TOKEN=...
```

Ottieni le credenziali OAuth via Google Cloud Console → API & Services → Credentials.

## Wrapper

```python
import sys
sys.path.insert(0, '/var/abchat/shared/core/tools/lib')  # or your brain's lib path
from gcalendar import list_events, create_event, delete_event
```

## Intent Detection

```python
args = "$ARGUMENTS".strip().lower()

if not args or any(w in args for w in ["lista", "show", "mostra", "vedi"]):
    intent = "list"
elif any(w in args for w in ["oggi", "today"]):
    intent = "today"
elif any(w in args for w in ["settimana", "week", "prossimi"]):
    intent = "week"
elif any(w in args for w in ["crea", "aggiungi", "nuovo", "add", "new"]):
    intent = "create"
elif any(w in args for w in ["modifica", "sposta", "cambia", "update", "edit"]):
    intent = "update"
elif any(w in args for w in ["cancella", "elimina", "delete", "rimuovi"]):
    intent = "delete"
else:
    intent = "list"
```

## Comandi

- `/calendar` → lista prossimi 7 giorni
- `/calendar oggi` → solo eventi di oggi
- `/calendar settimana` → prossimi 7 giorni dettagliati
- `/calendar crea "Riunione" domani alle 14:00 per 1 ora` → crea evento
- `/calendar crea "Call con Mario" 2026-04-10 10:00-11:00 [partecipanti: mario@example.com]`
- `/calendar modifica riunione sposta alle 15:00` → cerca e sposta
- `/calendar cancella riunione domani` → cerca e cancella con conferma

## Parsing date NLP

Interpreta linguaggio naturale per le date:
- "domani" → tomorrow
- "lunedì prossimo" → next monday
- "alle 14" → 14:00
- "per 1 ora" → duration 60min
- "15:00-16:30" → start/end espliciti
- "tutto il giorno" → all-day event

## Output atteso

### `/calendar` (lista)
```
📅 Prossimi 7 giorni

Lun 30/03
  10:00-11:00  Call con cliente
  14:00-15:00  Riunione team

Mar 31/03
  09:00        ☀️ Tutto il giorno: Festivita

Mer 01/04
  (niente)
```

## Calendar ID

Default: `primary` (calendario principale).
Per calendari multipli: configura `GCAL_CALENDAR_ID` in `.env` o in `wiki/skills/calendar.md`.

## Args Provided:
```
$ARGUMENTS
```
