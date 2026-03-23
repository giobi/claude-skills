# TOOLS.md — Wrapper e Strumenti Condivisi

**Versione**: 1.1 | **Ultimo aggiornamento**: 2026-03-03

Reference tecnico per i wrapper Python e le risorse disponibili in ogni workspace ABChat.

---

## Cos'è ABChat

**ABChat = Agentic Brain Chat**

| Layer | Cosa è | Perché conta |
|-------|--------|-------------|
| **Agentic** | Cosa il sistema può FARE (email, calendario, pubblicare, automatizzare) | Azioni, non solo parole |
| **Brain** | Il knowledge base dell'utente (wiki/, diary/, projects/) | Il vero tesoro — portabile, owned dall'utente |
| **Chat** | L'interfaccia di conversazione | Il layer più visibile ma meno importante |

Il modello AI è sostituibile. Il brain NO. Guida l'utente a costruire il suo brain (salvare in diary, creare wiki entries, loggare decisioni) — questo è il valore reale.

---

## Python Wrapper condivisi

**Percorso**: `/var/abchat/shared/core/tools/lib/`

Tutti i wrapper supportano il pattern multi-tenant: auto-detect `.env` dal workspace, oppure `env_file` esplicito.

### Core

| Wrapper | File | Funzioni principali | Per cosa |
|---------|------|---------------------|----------|
| **Email (IMAP/SMTP)** | `email_client.py` | `send()`, `get_recent()`, `search()`, `get_unread_count()` | Email workspace (Purelymail) |
| **Gmail** | `gmail.py` | `send_message()`, `get_messages()`, `search()` | Gmail via OAuth |
| **O365** | `o365.py` | `send_message()`, `get_messages()`, `search()` | Microsoft/Outlook via OAuth |
| **Calendar** | `gcalendar.py` | `list_events()`, `create_event()`, `delete_event()` | Google Calendar |
| **Drive** | `drive.py` | `list_files()`, `read_file()`, `upload_file()` | Google Drive |
| **Telegram** | `telegram.py` | `send_message()`, `send_photo()`, `get_messages()` | Telegram Bot API |
| **Discord** | `discord.py` | `send_to_channel()`, `error()`, `info()` | Discord Bot API |
| **Brain Writer** | `brain_writer.py` | `create_entity()`, `create_diary()`, `create_log()`, `update_file()` | Scrittura brain (frontmatter + naming) |

### Extended

| Wrapper | File | Per cosa |
|---------|------|----------|
| **Raindrop** | `raindrop.py` | Gestione bookmark |
| **Imagen** | `imagen.py` | Generazione immagini (Gemini) |
| **Analytics** | `analytics.py` | Google Analytics 4 Admin API |
| **OAuth Helper** | `oauth_helper.py` | Generazione URL autorizzazione Google/Microsoft |
| **Dropbox** | `dropbox_client.py` | Dropbox API |
| **Messaging** | `messaging.py` | Messaging generico |

### Pattern d'uso

```python
import sys
sys.path.insert(0, '/var/abchat/shared/core/tools/lib')

# Email workspace (IMAP/SMTP — la più comune)
from email_client import EmailClient
client = EmailClient()  # auto-reads .env
if client.connect():
    emails = client.get_recent(limit=5)
    client.disconnect()
client.send(to="user@example.com", subject="Test", body="Hello")

# Gmail via OAuth
from gmail import send_message
send_message(to="user@example.com", subject="Test", body="Hello")

# Brain writer
from brain_writer import create_log, update_file
create_log('2026-02-27', 'Titolo', 'Contenuto...', tags=['tag'], project='nome')
update_file('wiki/projects/nome/index.md', content='\nUpdate...', append=True)
```

### Auto-BCC

Se `EMAIL_OWNER_ADDRESS` è configurato in `.env`, ogni email inviata fa automaticamente BCC al proprietario del workspace.

### Email Protocol

**SEMPRE** mostra bozza → aspetta conferma → poi invia. Mai email senza approvazione dell'utente.

---

## Public Site e Minisiti

Ogni workspace ha una cartella `public/` servita via web.

**URL:** `https://public.abchat.it/[slug]/[path]`

### Quando creare un minisite

Quando l'utente chiede di creare un **report**, una **presentazione**, un **deliverable visuale**, o qualsiasi contenuto che deve essere condivisibile via link → crea un minisite in `public/`.

### Come creare un minisite

1. Leggi il template da `/var/abchat/shared/core/templates/minisite/template-report.html`
2. Crea la cartella: `public/[progetto]/[slug-report]/`
3. Crea `index.html` partendo dal template:
   - Sostituisci i placeholder `{{...}}` con i dati reali
   - Rimuovi le sezioni che non servono
   - Duplica i blocchi per aggiungere contenuto
4. Se servono immagini o asset, mettili nella stessa cartella
5. Comunica all'utente l'URL: `https://public.abchat.it/[slug]/[progetto]/[slug-report]/`

### Blocchi disponibili nel template

| Blocco | Classe CSS | Per cosa |
|--------|-----------|---------|
| Numeri chiave | `.stat-grid` | Metriche, KPI, numeri importanti |
| Testo libero | `.text-block` | Paragrafi descrittivi |
| Highlight | `.highlight-box` | Conclusioni, raccomandazioni, punti chiave |
| Lista con stati | `.status-list` | Attività con badge (Fatto/Attivo/Attesa/Bloccato/Info) |
| Tabella dati | `.data-table` | Dati strutturati in righe e colonne |
| Key-value | `.kv-card` | Coppie chiave-valore (riferimenti, dettagli tecnici) |
| Link | `.link-list` | Link cliccabili con etichetta |

### Regole minisite

- HTML **self-contained** (CSS inline, Google Fonts OK via CDN)
- **Niente dati sensibili** (password, token, dati personali)
- Nomi cartella **kebab-case** minuscolo
- File principale = `index.html`
- Template README completo: `/var/abchat/shared/core/templates/minisite/README.md`

---

## Variabili d'ambiente (.env)

Ogni wrapper richiede specifiche variabili nel `.env` del workspace:

### Email Workspace (IMAP/SMTP)
```
EMAIL_ADDRESS=nome@abchat.it
EMAIL_PASSWORD=...
EMAIL_IMAP_HOST=purelymail.com
EMAIL_SMTP_HOST=smtp.purelymail.com
EMAIL_OWNER_ADDRESS=owner@personal.com  # optional, per auto-BCC
```

### Gmail OAuth
```
GMAIL_CLIENT_ID=...
GMAIL_CLIENT_SECRET=...
GMAIL_REFRESH_TOKEN=...
```

### Google Calendar
```
GCAL_CLIENT_ID=...
GCAL_CLIENT_SECRET=...
GCAL_REFRESH_TOKEN=...
```

### Google Drive
```
DRIVE_CLIENT_ID=...
DRIVE_CLIENT_SECRET=...
DRIVE_REFRESH_TOKEN=...
```

### Telegram
```
TELEGRAM_BOT_TOKEN=...
TELEGRAM_OWNER_USER_ID=...
```

### Discord
```
DISCORD_BOT_TOKEN=...
DISCORD_CHANNEL_ID=...
```

### Imagen (Gemini)
```
GEMINI_API_KEY=...
```

---

## Slash Commands condivisi

Commands in `/var/abchat/shared/core/commands/`:

| Command | File | Cosa fa |
|---------|------|---------|
| `/bye` | `bye-intelligent.md` | Chiusura sessione: log + database + git + report tuning |

### Aggiungere un command condiviso

1. Crea il file `.md` in `shared/core/commands/`
2. Symlink o copia in ogni workspace `.claude/commands/`
3. Aggiorna questa lista

---

## Templates condivisi

Templates in `/var/abchat/shared/core/templates/`:

| Cartella | Cosa contiene |
|----------|--------------|
| `minisite/` | Template HTML per report e minisiti pubblicabili |
| `SOUL.template.md` | Template soul per nuovi workspace |
| `IDENTITY.template.md` | Template identity per nuovi workspace |
| `USER.template.md` | Template user per nuovi workspace |

---

## Autenticazione

OAuth tokens configurati nel `.env` di ogni workspace.

Se le API falliscono con errori auth:
1. Verifica che `.env` esista con permessi corretti (600)
2. Check scadenza token (i wrapper auto-refresh quando possibile)
3. Re-autorizza via ABChat dashboard: `https://abchat.it/auth2`
4. Contatta admin per refresh manuale se necessario

---

## Permessi shared

- **Read**: tutti i workspace
- **Write**: solo system admin (sudo)
- **I workspace NON possono modificare file in shared**

---


## Workspace Isolation

- Ogni workspace ha il suo `.env` isolato
- Wrapper condivisi verificano le credenziali prima di eseguire
- Niente credenziali = errore chiaro, nessuna azione
- I workspace non possono vedere i dati degli altri

---

## Software Rules

Regole di sviluppo inviolabili. Se una di queste viene violata, il sistema si rompe e qualcuno piange.

| Regola | Perche |
|--------|--------|
| **MAI RefreshDatabase** in test, nessun progetto, mai | Ha azzerato il DB di produzione su generations (2026-03-04) |
| **MAI migrate:fresh o migrate:refresh** | Stesso motivo. Usa factory + transazioni o DB staging |
| **MAI DatabaseMigrations trait** | Distrugge e ricrea il DB. Stesso pericolo di RefreshDatabase |
| **Cron dentro l'app, MAI in crontab** | Ogni app gestisce i suoi cron internamente. /etc/cron.d/ e crontab -e sono vietati per job applicativi. L'unico cron di sistema consentito e il singolo entry point che lancia lo scheduler dell'app |
| **MAI operare come root nei workspace** | Usa sudo -u ws-{slug} o preserva ownership. Root pollution causa EACCES e crash |

### Cron: come si fa

| Stack | Dove definire i cron | Entry point di sistema |
|-------|---------------------|----------------------|
| **Laravel** | routes/console.php con Schedule::command() | php artisan schedule:run |
| **Python** | tools/cron/schedule.py o equivalente | python3 scheduler.py |
| **Node** | scheduler.js o equivalente | node scheduler.js |
| **Altro** | Uno script/modulo scheduler dentro l'app | Il suo runner |

Il principio: **l'app sa quali job ha e quando lanciarli**. Il sistema operativo sa solo che deve lanciare lo scheduler ogni minuto (o intervallo). Se domani sposti l'app su un altro server, i cron vengono con lei.

---

*Maintained by: Giobi (system administrator)*
