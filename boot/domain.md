# Domain: ABChat

domain: abchat.giobi.com
admin: Giobi Fasoli <giobi@giobi.com>

Piattaforma per brain personali. Ogni brain è un workspace isolato
con il proprio utente di sistema (ws-{slug}).

## Limiti del domain

- No SSH, no sudo, no git push
- No accesso ad altri brain
- No modifica di file in shared/

## Roles

| Role | Può fare |
|------|----------|
| root | Tutto — SSH, sudo, gestire shared, creare/eliminare brain |
| admin | Gestire brain assegnati, accesso parziale a shared |
| user | Solo il proprio brain e i tool configurati |
| agent | Automazione senza umano, task specifici |

Role in `.env` → `BRAIN_ROLE` (default: user).

## Supporto

Problemi infrastruttura → contattare Giobi.
