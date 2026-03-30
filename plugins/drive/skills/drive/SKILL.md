---
name: drive
description: "Google Drive organizer — audit, triage inbox, split PDF, rename, move"
user-invocable: true
argument-hint: "[audit | triage | split <filename> | rename | cleanup | status]"
requires:
  env:
    - DRIVE_CLIENT_ID
    - DRIVE_CLIENT_SECRET
    - DRIVE_REFRESH_TOKEN
  packages:
    - requests
    - pypdf
---

**Google Drive Organizer** — Tieni Drive in ordine senza sforzo

## NLP-First

Interpreta linguaggio naturale:
- `/drive` → audit rapido (orfani root + inbox + recenti)
- `/drive audit` → audit completo struttura
- `/drive triage` → processa inbox e orfani root
- `/drive split nomefile.pdf` → splitta PDF multi-documento
- `/drive rename` → proponi rinominazione file recenti
- `/drive cleanup` → rimuovi file vuoti, duplicati, junk
- `/drive status` → stats rapide
- `ho caricato un pdf su drive` → cerca il piu recente, leggilo, proponi azione
- `metti su drive questo file` → upload + naming + cartella giusta
- `cerca su drive X` → ricerca per nome/tipo/data

## Wrapper

```python
import sys
sys.path.insert(0, '/var/abchat/shared/core/tools/lib')  # or your brain's lib path
from drive import (
    list_files, search_files, upload_file, move_file,
    delete_file, create_folder, get_file_metadata
)
```

## Configuration

La configurazione specifica (struttura cartelle, regole di classificazione, naming patterns) e in `wiki/skills/drive.md`. Leggila SEMPRE prima di operare.

## Subcommands

### `/drive` o `/drive audit`

Audit rapido:
1. File orfani in root (non in cartelle)
2. File nella inbox da smistare
3. Ultimi 10 file modificati
4. Anomalie (file enormi, nomi brutti, duplicati)

### `/drive triage`

Per ogni file in inbox e ogni orfano in root:
1. Identifica tipo (PDF, doc, sheet)
2. Leggi nome → deduci categoria usando le regole in `wiki/skills/drive.md`
3. Proponi destinazione
4. Confidence > 80% → sposta automaticamente
5. Confidence bassa → chiedi conferma

### `/drive split <filename>`

1. Cerca il file su Drive per nome
2. Scaricalo in `storage/tmp/`
3. Leggilo pagina per pagina (PDF)
4. Identifica documenti separati (cambio layout/intestazione)
5. Splitta con pypdf
6. Rinomina: `YYYY-MM-DD-descrizione.pdf`
7. Chiedi conferma destinazione per ogni pezzo
8. Uploada e trasha l'originale

### `/drive rename`

Cerca file con nomi brutti e proponi rinominazione:
- `Digitalizzato_*` → `YYYY-MM-DD-descrizione.ext`
- `IMG_XXXX.*` → `YYYY-MM-DD-descrizione.ext`
- `Copia di ...` → rimuovi prefisso
- `(1)`, `(2)` → segnala duplicati
- Target: `YYYY-MM-DD-slug-descrizione.ext` (lowercase, hyphens)

### `/drive cleanup`

1. Cartelle vuote → proponi eliminazione
2. File `.DS_Store` → elimina
3. Duplicati (stesso nome + size) → segnala
4. Orfani root → proponi spostamento

### `/drive status`

Quick stats: totale file/cartelle, aggiunti ultima settimana, orfani, inbox, anomalie.

## Modalita autonoma

Quando eseguito senza utente interattivo (cron/scheduler):
- Solo confidence > 90% → sposta automaticamente
- Resto → logga in `storage/drive-triage-log.yaml`
- Report via Discord/Telegram
- **MAI cancellare in autonomo** — solo spostare

## Post-azione

Dopo operazioni significative, valuta se aggiornare wiki:
- File medici → `wiki/projects/personal/health/` (bloodwork.yaml, visits.yaml)
- File fiscali → progetto rilevante
- PDF processati → estrai dati strutturati se possibile

## Sicurezza

- **MAI cancellare permanentemente** — sempre trash
- **Conferma** prima di batch su 5+ file
- **Niente dati sensibili nei log** — solo nomi file
- Rispetta le cartelle protette definite in `wiki/skills/drive.md`

