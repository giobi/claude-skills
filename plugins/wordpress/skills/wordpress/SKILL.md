---
name: wordpress
description: "WordPress management — posts, plugins, users, WP-CLI, login testing, GDPR"
user-invocable: true
argument-hint: "[sito] [azione] — es: /wordpress blog.giobi.com lista post"
requires:
  env:
    - "{SITE_PREFIX}_USERNAME"
    - "{SITE_PREFIX}_APP_PASSWORD"
    - "{SITE_PREFIX}_URL"
  packages:
    - requests
    - pyyaml
---

# /wordpress — WordPress Manager

Gestione completa WordPress: REST API, WP-CLI, Puppeteer, multi-sito.

## Setup

### 1. Configura i siti in wiki/projects

Ogni sito WordPress nel brain ha un frontmatter nel suo `wiki/projects/*/index.md`:

```yaml
wordpress:
  url: https://example.com
  env_prefix: EXAMPLE_WP
```

### 2. Aggiungi credenziali al `.env`

```
EXAMPLE_WP_URL=https://example.com
EXAMPLE_WP_USERNAME=admin
EXAMPLE_WP_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
```

**App Password** (non la password normale!):
WordPress Admin → Users → Profile → Application Passwords → Generate

### 3. Sito default (opzionale)

In `wiki/skills/wordpress.md`, aggiungi:
```yaml
default_site: example.com
```

Se non configurato, usa il primo sito trovato in wiki/projects o richiede sito esplicito.

## Comandi

```
/wordpress                              Lista siti configurati
/wordpress example.com                  Info sito + stats
/wordpress example.com lista post       Lista post recenti
/wordpress example.com nuovo post       Crea draft interattivo
/wordpress example.com pubblica <id>    Pubblica draft
/wordpress example.com plugin           Lista plugin + stato
/wordpress example.com plugin update    Aggiorna tutti i plugin
/wordpress example.com utenti           Lista utenti
/wordpress example.com nuovo utente     Crea utente
/wordpress example.com magic login      Genera link login temporaneo
/wordpress example.com test login       Verifica login con Puppeteer
/wordpress example.com privacy policy   Genera privacy policy GDPR
/wordpress example.com cookie banner    Verifica cookie banner attivo
/wordpress example.com wpcli <cmd>      Esegui WP-CLI via SSH
```

## Wrapper Python

```python
import sys
sys.path.insert(0, '.claude/skills/wordpress')
from wordpress import (
    create_draft,      # (title, content, tags=[], site=None) → dict
    get_posts,         # (limit=10, status='any', site=None) → list
    update_post,       # (post_id, data, site=None) → dict
    publish_post,      # (post_id, site=None) → dict
    get_sites,         # () → dict of configured sites
    upload_media,      # (file_path, site=None) → dict
)

# Lista siti configurati (da wiki/projects)
sites = get_sites()

# Crea draft
post = create_draft(
    title="Il mio post",
    content="<p>Contenuto HTML</p>",
    tags=["tag1", "tag2"],
    site="example.com"   # opzionale se hai un default
)

# Pubblica post esistente
result = publish_post(post_id=42, site="example.com")
```

## Configurazione Multi-Sito

Il wrapper scansiona `wiki/projects/*/index.md` cercando il blocco `wordpress:` nel frontmatter.
Ogni sito viene registrato automaticamente — nessuna configurazione manuale dell'agente necessaria.

```python
sites = get_sites()
# → {
#     "example.com": {"url": "https://example.com", "username": "admin", ...},
#     "altro.it":    {"url": "https://altro.it", ...}
# }
```

## WP-CLI (SSH)

Per operazioni non disponibili via REST API, usa WP-CLI via SSH:

```bash
# Esempi comuni
wp plugin list --status=active
wp user list
wp post list --post_status=draft
wp option get siteurl
wp cache flush
wp search-replace 'vecchio.com' 'nuovo.com' --dry-run
```

Prima di eseguire: verifica SSH configurato in `wiki/projects/{sito}/index.md` con host e credenziali.

## Puppeteer (verifica visiva)

Per test login, cookie banner, visual check — usa la skill `playw` o `playralph`:

```python
# Test login
# 1. Genera magic login link
# 2. Apri con Playwright
# 3. Verifica pagina caricata correttamente
# 4. Screenshot per conferma visiva
```

## Magic Login Link

Genera link login temporaneo senza password (via plugin o WP-CLI):

```bash
# Con WP-CLI
wp user generate-magic-link --user=mario@example.com --expiry=3600
```

Oppure via plugin "Magic Login" se installato.

## GDPR / Cookie Banner

Per generare privacy policy o verificare cookie banner:

1. **Privacy policy**: genera testo GDPR-compliant dal template, inserisce via REST API come pagina
2. **Cookie banner**: usa Playwright per verificare che il banner appaia alla prima visita (navigazione in incognito)

## Intent Detection

```python
args = "$ARGUMENTS".strip()
parts = args.split()

# Detect sito (primo argomento con punto o configurato come default)
site = None
action = args

if parts and ("." in parts[0] or parts[0] in get_sites()):
    site = parts[0]
    action = " ".join(parts[1:]).lower()
else:
    action = args.lower()

# Detect azione
if any(w in action for w in ["lista", "list", "post"]):
    intent = "list_posts"
elif any(w in action for w in ["nuovo", "crea", "draft", "scrivi"]):
    intent = "create_post"
elif any(w in action for w in ["plugin"]):
    intent = "plugins"
elif any(w in action for w in ["utent", "user"]):
    intent = "users"
elif any(w in action for w in ["magic", "login link"]):
    intent = "magic_login"
elif any(w in action for w in ["test login", "verifica login"]):
    intent = "test_login"
elif any(w in action for w in ["privacy", "gdpr"]):
    intent = "privacy_policy"
elif any(w in action for w in ["cookie", "banner"]):
    intent = "cookie_banner"
elif any(w in action for w in ["wpcli", "wp-cli", "wp "]):
    intent = "wpcli"
else:
    intent = "site_info"  # default: mostra info sito
```
