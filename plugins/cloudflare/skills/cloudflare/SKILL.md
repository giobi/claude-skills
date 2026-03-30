---
name: cloudflare
description: "Cloudflare DNS — zones, records, cache purge, R2, Pages"
user-invocable: true
argument-hint: "[dns <domain> | record add/del | cache purge | zone list | pages list]"
requires:
  env:
    - CLOUDFLARE_API_TOKEN
  packages:
    - requests
---

# /cloudflare — Cloudflare Manager

Gestisci DNS, cache, R2 e Pages via Cloudflare API.

## Setup

```
CLOUDFLARE_API_TOKEN=your_api_token
```

Token: Cloudflare Dashboard → My Profile → API Tokens → Create Token.
Permessi minimi: `Zone:DNS:Edit`, `Zone:Cache Purge:Purge`, `Zone:Zone:Read`.

## Wrapper

```python
import sys
sys.path.insert(0, '.claude/skills/cloudflare')
from cloudflare import (
    dns_list_zones, dns_find_zone,
    dns_list_records, dns_create_record, dns_update_record, dns_delete_record,
    cache_purge_zone, cache_purge_urls,
    r2_list_buckets,
    pages_list_projects,
)
```

## Intent Detection

```python
args = "$ARGUMENTS".strip().lower()

if any(w in args for w in ["zone", "domini", "list"]) and "record" not in args:
    intent = "list_zones"
elif any(w in args for w in ["dns", "record", "records"]):
    if any(w in args for w in ["add", "crea", "aggiungi", "nuovo"]):
        intent = "add_record"
    elif any(w in args for w in ["del", "cancella", "rimuovi", "remove"]):
        intent = "delete_record"
    else:
        intent = "list_records"
elif any(w in args for w in ["cache", "purge", "svuota"]):
    intent = "purge_cache"
elif any(w in args for w in ["r2", "bucket", "storage"]):
    intent = "r2"
elif any(w in args for w in ["pages", "deploy"]):
    intent = "pages"
else:
    intent = "list_zones"
```

## Comandi

### DNS
- `/cloudflare zone list` → lista tutti i domini nell'account
- `/cloudflare dns example.com` → lista record DNS di un dominio
- `/cloudflare dns add example.com A www 1.2.3.4` → aggiungi record A
- `/cloudflare dns add example.com CNAME blog wordpress.com` → aggiungi CNAME
- `/cloudflare dns del example.com A www` → elimina record (con conferma)
- `/cloudflare dns add example.com MX @ mail.example.com priority:10` → MX record

### Cache
- `/cloudflare cache purge example.com` → purge intera zone
- `/cloudflare cache purge example.com/pagina` → purge URL specifico

### R2 / Pages
- `/cloudflare r2` → lista bucket R2
- `/cloudflare pages` → lista Pages projects

## Record types supportati
A, AAAA, CNAME, MX, TXT, NS, SRV, CAA

## Output atteso

### `/cloudflare dns example.com`
```
DNS Records — example.com (zone: abc123)

TYPE   NAME        CONTENT              TTL    PROXY
A      @           1.2.3.4              auto   ✓ proxied
A      www         1.2.3.4              auto   ✓ proxied
CNAME  mail        mail.provider.com    auto   ✗ dns-only
MX     @           mx1.provider.com     auto   ✗ dns-only  (pri: 10)
TXT    @           v=spf1 ...           auto   ✗ dns-only
```

## Note
- Operazioni distruttive (delete record) → conferma sempre
- Il wrapper auto-legge `CLOUDFLARE_API_TOKEN` da `.env`
- Usa `dns_find_zone(domain)` per risolvere domain → zone_id automaticamente
