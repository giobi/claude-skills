---
name: linkedin
description: LinkedIn intelligence — query builder, result parser, Proxycurl integration. Usata da /stalker e invocabile standalone per ricerche LinkedIn.
argument-hint: "[nome] [--company X] [--location Y]"
---

# LinkedIn Intelligence

**Input**: `$ARGUMENTS`

## Cosa fa

Ricerca profili LinkedIn via dork queries + parsing risultati + Proxycurl API (opzionale).

**NON cerca da sola** — genera query ottimizzate, l'agente fa WebSearch, poi questa skill parsa i risultati.

## Requisiti

- Nessuno per query building/parsing
- `PROXYCURL_API_KEY` nel `.env` per lookup strutturati (opzionale)

## Wrapper

Lo script `${CLAUDE_SKILL_DIR}/scripts/linkedin.py` fornisce tutte le funzioni:

```python
import sys; sys.path.insert(0, '${CLAUDE_SKILL_DIR}/scripts')
from linkedin import build_queries, parse_search_results, proxycurl_lookup, stalker_linkedin_block

# Genera query ottimizzate per WebSearch
queries = build_queries("Mario Rossi", company="Emisfera", location="Verbania")
# → ['site:linkedin.com/in/ "Mario Rossi" "Emisfera" "Verbania"', ...]

# Parsa risultati WebSearch in profili strutturati
profiles = parse_search_results(websearch_results)
# → [{"name": ..., "headline": ..., "current_company": ..., "url": ...}]

# Proxycurl per dati completi (se configurato)
full = proxycurl_lookup("https://linkedin.com/in/mario-rossi-123/")

# Piano completo per stalker
plan = stalker_linkedin_block("Mario Rossi", company="Emisfera", level=7)
```

## Funzioni disponibili

| Funzione | Cosa fa |
|----------|---------|
| `build_queries(name, company, location, role)` | Query dork dal piu specifico al piu ampio |
| `build_employee_queries(company, roles)` | Query per trovare dipendenti |
| `parse_search_results(results)` | Estrae profili strutturati dai risultati WebSearch |
| `parse_linkedin_title(title)` | Parsa "Nome - Ruolo - Azienda \| LinkedIn" |
| `parse_profile_url(url)` | Metadata da URL LinkedIn |
| `parse_company_page(results)` | Estrae company page dai risultati |
| `proxycurl_lookup(url)` | Profilo completo via API (se configurato) |
| `proxycurl_company(url)` | Company completa via API |
| `proxycurl_search(name, company, role, location)` | Ricerca persone via API |
| `stalker_linkedin_block(name, ...)` | Piano completo con query + azioni raccomandate |

## CLI (per test)

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/linkedin.py --queries "Mario Rossi" --company "Emisfera"
python3 ${CLAUDE_SKILL_DIR}/scripts/linkedin.py --proxycurl "https://linkedin.com/in/mario-rossi/"
python3 ${CLAUDE_SKILL_DIR}/scripts/linkedin.py --plan "Mario Rossi" --company "Emisfera" --level 7
```

## Uso standalone

```
/linkedin Mario Rossi lavora a Emisfera Verbania
```

Genera query, cerca via WebSearch, parsa risultati, mostra profili trovati. Se Proxycurl disponibile, arricchisce con dati strutturati.

## Uso da altre skill

Altre skill (es. `/stalker`) possono invocare `/linkedin` per la parte LinkedIn della ricerca.
