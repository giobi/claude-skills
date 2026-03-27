---
name: discord
description: "Discord — send messages to channels, DMs, and project channels"
user-invocable: true
argument-hint: "[messaggio | dm: msg | #canale msg | project:nome msg]"
requires:
  env:
    - DISCORD_BOT_TOKEN
    - DISCORD_DEFAULT_CHANNEL
---

# /discord — Discord Bot

Invia messaggi su Discord tramite Bot API. Supporta canali, webhook e routing per progetto.

## Setup

### 1. Crea il bot

1. Vai su https://discord.com/developers/applications
2. New Application → Bot → Reset Token → copia il token
3. Permissions necessarie: `Send Messages`, `Read Message History`, `View Channels`
4. Invita il bot: usa l'OAuth2 URL Generator nel pannello sviluppatori con scope `bot` e le permissions sopra

### 2. Ottieni gli ID

Abilita Developer Mode (Settings → Advanced → Developer Mode), poi:
- **Channel ID**: tasto destro sul canale → Copy Channel ID
- **Server ID**: tasto destro sul server → Copy Server ID
- **User ID**: tasto destro sul profilo → Copy User ID

### 3. Configura `.env`

```
DISCORD_BOT_TOKEN=Bot_token_here
DISCORD_DEFAULT_CHANNEL=1234567890123456789   # canale principale notifiche
DISCORD_DM_CHANNEL=9876543210987654321        # opzionale — canale privato/DM
DISCORD_GUILD_ID=1111111111111111111          # opzionale — ID server
DISCORD_OWNER_USER_ID=2222222222222222222     # opzionale — per DM diretti
DISCORD_WEBHOOK_URL=https://discord.com/...  # opzionale — alternativa al bot
```

## Comandi

```
/discord testo qui                    Invia sul canale default
/discord dm: testo                    Invia sul canale DM/privato
/discord #canale testo                Cerca canale per nome e invia
/discord project:nome testo           Invia sul canale del progetto
```

## Wrapper Python

```python
import sys, os
sys.path.insert(0, '.claude/skills/discord')
from discord import send_to_channel, send_webhook, read_messages

channel_id = os.getenv('DISCORD_DEFAULT_CHANNEL')
send_to_channel(channel_id, "Deploy completato ✅")

# Via webhook (più semplice, no bot necessario)
send_webhook(os.getenv('DISCORD_WEBHOOK_URL'), "Notifica da brain 🦉")
```

## Formattazione Discord

```
**grassetto**   *corsivo*   `codice inline`
\`\`\`blocco codice\`\`\`
> citazione
```

- Link: wrappa in `<url>` per evitare embed automatici
- Max 2000 caratteri per messaggio; spezza se supera il limite
- Tabelle: no supporto nativo — usa blocchi codice monospace

## Routing per Progetto

Se il tuo progetto ha un campo `discord_channel` nel frontmatter wiki:

```yaml
# wiki/projects/mioprogetto/index.md
---
discord_channel: "1234567890123456"
---
```

Il wrapper trova automaticamente il canale dal nome progetto.

## Intent Detection

```python
args = "$ARGUMENTS".strip()

if args.lower().startswith("dm:"):
    action, message = "dm", args[3:].strip()
elif args.startswith("#"):
    parts = args[1:].split(" ", 1)
    action = "channel_by_name"
    channel_name, message = parts[0], parts[1] if len(parts) > 1 else ""
elif args.lower().startswith("project:"):
    parts = args[8:].split(" ", 1)
    action = "project_channel"
    project_name, message = parts[0], parts[1] if len(parts) > 1 else ""
else:
    action, message = "default_channel", args
```
