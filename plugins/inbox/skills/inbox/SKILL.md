---
name: inbox
description: "Inbox management (list, process, status, clear)"
user-invocable: true
argument-hint: "[list|process|status|clear|show filename]"
---

# /inbox — Inbox Manager

Smista file da `inbox/` nelle destinazioni giuste del brain (diary/, wiki/, log/).

L'inbox è un punto di passaggio neutro. Qualsiasi fonte può depositare file lì — il comando si occupa di classificarli e archiviarli.

## Subcommands

```
/inbox              Status: file pendenti, statistiche per tipo
/inbox list         Lista file pendenti con preview
/inbox process      Processa tutti i file pendenti
/inbox show <file>  Mostra contenuto di un file specifico
/inbox clear        Sposta processati in inbox/processed/ (richiede conferma)
```

## Processing Flow

```
1. Leggi ogni file in inbox/
2. Classifica (diary / log / wiki) — vedi regole sotto
3. Estrai entità (persone, aziende, progetti) → crea wikilinks
4. Sposta nella destinazione via brain_writer
5. Commit + push
```

## Classificazione

Regole base (personalizzabili in `wiki/skills/inbox.md`):

- Keywords personali → `diary/`
- Keywords lavoro → `log/`
- Entità riconosciute (progetto, persona, azienda) → `wiki/`
- Default → `log/`

**Leggi sempre `wiki/skills/inbox.md`** prima di processare: contiene le keyword e le regole specifiche di questo brain.

## Entity Extraction

Per ogni file:
- Cerca nomi propri → check `wiki/people/`
- Cerca aziende → check `wiki/companies/`
- Cerca progetti → check `wiki/projects/`
- Crea `[[wikilinks]]` per entità trovate

## File Structure

```
inbox/              File in attesa di processing
inbox/processed/    File già processati (archivio)
```

## Sources

L'inbox accetta file da qualsiasi fonte. Esempi comuni:

| Fonte | Come deposita |
|-------|--------------|
| Discord bot | Salva messaggi come .md in inbox/ |
| Telegram bot | Idem via webhook |
| WhatsApp | Forward → script → inbox/ |
| Gmail | Filtro → script → inbox/ |
| Folder remoto | rsync/cron → inbox/ |
| CLI manuale | cp note.md inbox/ |
| Webhook esterno | POST → salva in inbox/ |

La configurazione di ogni source è in `wiki/skills/inbox.md`.

## Dipendenze Opzionali

Il comando funziona standalone. Se presenti, attiva integrazioni extra:

- **raindrop** skill → processa anche bookmark Raindrop pendenti
- **brain-writer** skill → scrittura con frontmatter corretto (consigliata)

## Args Provided

```
$ARGUMENTS
```
