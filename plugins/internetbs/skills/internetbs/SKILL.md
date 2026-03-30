---
name: internetbs
description: "Internet.bs — domain management: check, register, renew, DNS, nameservers"
user-invocable: true
argument-hint: "[list | check <domain> | info <domain> | dns <domain> | renew <domain> | register <domain>]"
requires:
  env:
    - INTERNETBS_API_KEY
    - INTERNETBS_PASSWORD
  packages:
    - requests
---

# /internetbs — Domain Manager

Gestisce domini via [Internet.bs API](https://internet.bs): lista, verifica disponibilità, registra, rinnova, DNS.

## Setup

Aggiungi al tuo `.env`:
```
INTERNETBS_API_KEY=your_api_key
INTERNETBS_PASSWORD=your_api_password
```

Ottieni credenziali su: https://internet.bs → My Account → API Access

## Comandi

```
/internetbs list                        Lista tutti i domini dell'account + scadenze
/internetbs check example.com           Verifica disponibilità + prezzo
/internetbs info example.com            Info complete (nameserver, contatti, scadenza)
/internetbs dns example.com             Lista record DNS
/internetbs dns add example.com A www 1.2.3.4
/internetbs dns remove example.com A www 1.2.3.4
/internetbs renew example.com [anni]    Rinnova dominio (default 1 anno)
/internetbs register example.com [anni] Registra nuovo dominio
/internetbs ns example.com              Mostra nameserver
/internetbs ns update example.com ns1.provider.com ns2.provider.com
/internetbs balance                     Saldo account
```

## Wrapper Python

```python
import sys
sys.path.insert(0, '.claude/skills/internetbs')
from internetbs import (
    list_domains,        # () → List[Dict]
    get_domain_info,     # (domain) → Dict
    check_availability,  # (domain) → bool
    get_nameservers,     # (domain) → List[str]
    update_nameservers,  # (domain, [ns1, ns2, ...]) → Dict
    purchase_domain,     # (domain, years=1, contacts=None) → Dict  ⚠️ costs money
    renew_domain,        # (domain, years=1, currency='USD') → Dict  ⚠️ costs money
    get_balance,         # () → Dict
    get_domain_price,    # (domain, currency='USD') → Dict
)
```

## Esecuzione

Parsa l'input NLP, poi esegui con il wrapper:

```python
import sys
sys.path.insert(0, '.claude/skills/internetbs')
from internetbs import list_domains, check_availability, get_domain_info

# Esempio: lista domini in scadenza entro 30 giorni
from datetime import datetime, timedelta
domains = list_domains()
soon = datetime.now() + timedelta(days=30)
expiring = [
    d for d in domains
    if d.get('expirationdate') and
    datetime.strptime(d['expirationdate'], '%m/%d/%Y') <= soon
]
```

## Regole

- **Operazioni di acquisto** (`register`, `renew`) costano soldi reali → mostra sempre prezzo + conferma prima di procedere
- La API restituisce date in formato `MM/DD/YYYY` → usa `parse_expiry_date()` per convertire in ISO
- In caso di errore API, mostra il campo `message` dalla risposta
- `list_domains()` senza `compact=True` fa una chiamata più lenta ma ritorna tutti i dettagli

## Output atteso

### `/internetbs list`
```
Domenico (42 domini)

✅ = attivo  ⚠️ = scade entro 30gg  🔴 = scade entro 7gg

example.com          scade 2026-11-19  ✅
another.net          scade 2025-12-01  🔴  ← rinnova!
...
```

### `/internetbs check example.com`
```
example.com
Status: ✅ Disponibile
Prezzo registrazione: $12.99/anno
Prezzo rinnovo: $12.99/anno
```
