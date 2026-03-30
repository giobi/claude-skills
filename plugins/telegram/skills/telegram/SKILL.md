---
name: telegram
description: "Telegram — send messages, read inbox, manage bot interactions"
user-invocable: true
argument-hint: "[manda: testo | inbox | leggi | status]"
requires:
  env:
    - TELEGRAM_BOT_TOKEN
    - TELEGRAM_CHAT_ID
  packages:
    - requests
    - python-dotenv
---

# /telegram — Telegram Bot

Invia e riceve messaggi tramite Telegram Bot API. Supporta testo, foto, file e lettura messaggi in arrivo.

## Setup

### 1. Crea il bot
1. Apri Telegram e cerca `@BotFather`
2. `/newbot` → scegli nome e username
3. Copia il **Bot Token**

### 2. Ottieni il Chat ID
Avvia una conversazione con il bot, poi chiama l'endpoint `getUpdates` delle Telegram API.
Il campo `chat.id` del tuo messaggio è il `TELEGRAM_CHAT_ID`.

### 3. Configura `.env`
```
TELEGRAM_BOT_TOKEN=1234567890:ABCdef...
TELEGRAM_CHAT_ID=123456789
TELEGRAM_OWNER_USER_ID=123456789       # opzionale — per auth check
TELEGRAM_OWNER_USERNAME=tuousername    # opzionale — per auth check
```

### 4. Architettura messaggi in arrivo

Il wrapper usa un'architettura webhook → SQLite:
- Configura un webhook Telegram che salva aggiornamenti in un DB locale
- `get_messages()` legge dal DB locale (no polling, nessuna race condition)

Per setup semplice senza webhook: usa `requests.get` sull'endpoint `getUpdates` di Telegram Bot API.

## Comandi

```
/telegram manda: testo              Manda messaggio al TELEGRAM_CHAT_ID
/telegram manda foto: /path/img.jpg Invia foto
/telegram inbox                     Leggi messaggi non letti
/telegram leggi                     Leggi ultimi messaggi
/telegram status                    Verifica bot attivo + chat_id
```

## Wrapper Python

```python
import sys
sys.path.insert(0, '.claude/skills/telegram')
from telegram import (
    send_message,      # (chat_id, text, parse_mode='HTML') → dict
    send_photo,        # (chat_id, photo_path, caption=None) → dict
    send_document,     # (chat_id, file_path, caption=None) → dict
    get_messages,      # (unread_only=True, env_file=None) → List[dict]
    get_chat_id,       # () → dict con chat_id o None
    is_authorized,     # (user_id, username) → bool
    sanitize_html,     # (text) → str — escape HTML per parse_mode HTML
)
```

## Esempi

```python
import sys, os
sys.path.insert(0, '.claude/skills/telegram')
from telegram import send_message

chat_id = os.getenv('TELEGRAM_CHAT_ID')

# Testo semplice
send_message(chat_id=chat_id, text="Ciao dal brain! 🦉")

# HTML formattato
send_message(
    chat_id=chat_id,
    text="<b>Deploy completato</b>\n<code>v2.3.1</code> su produzione",
    parse_mode='HTML'
)
```

## Formattazione HTML

```
<b>grassetto</b>   <i>corsivo</i>   <code>codice inline</code>
<pre>blocco codice</pre>   <a href="url">link</a>
```

Usa `sanitize_html(text)` per fare escape del testo dinamico prima di inserirlo in tag HTML.

## Limiti

- Max 4096 caratteri per messaggio
- Max 50MB per file
- Rate limit: 30 msg/sec per bot, 20 msg/min per chat

## Intent Detection

```python
args = "$ARGUMENTS".strip().lower()

if any(w in args for w in ["manda", "invia", "send"]):
    action = "send"
elif any(w in args for w in ["foto", "photo", "immagine"]):
    action = "send_photo"
elif any(w in args for w in ["inbox", "leggi", "read", "unread"]):
    action = "read"
elif any(w in args for w in ["status", "check", "stato"]):
    action = "status"
else:
    action = "send"  # default: testo come messaggio
```
