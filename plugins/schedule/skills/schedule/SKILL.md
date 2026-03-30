---
name: schedule
description: "Schedule manager (list, show, add, edit, disable, enable, delete)"
user-invocable: true
argument-hint: "[list|show|add|edit|disable|enable|delete] [args]"
requires:
  capabilities:
    - scheduling  # brain scheduler (tools/cron/schedule.py + Task API)
---

**Schedule Manager** - CRUD per i task schedulati nel brain scheduler

## Setup

Richiede che il brain abbia il scheduler configurato in `tools/cron/schedule.py` con la `Task()` fluent API.
Vedi `boot/local.yaml` → `capabilities.scheduling`.

Il path del file è relativo alla root del brain: `tools/cron/schedule.py`.

## Intent Detection

```python
args = "$ARGUMENTS".strip().lower()

if not args or any(w in args for w in ["list", "ls", "mostra", "tutti", "status"]):
    intent = "list"
elif any(w in args for w in ["show", "vedi", "dettaglio", "info"]):
    intent = "show"
elif any(w in args for w in ["add", "aggiungi", "nuovo", "crea", "create", "new"]):
    intent = "add"
elif any(w in args for w in ["edit", "modifica", "cambia", "change", "frequenza", "orario"]):
    intent = "edit"
elif any(w in args for w in ["disable", "disabilita", "spegni", "off", "pausa", "stop", "commenta"]):
    intent = "disable"
elif any(w in args for w in ["enable", "abilita", "accendi", "on", "riattiva", "attiva", "start"]):
    intent = "enable"
elif any(w in args for w in ["delete", "elimina", "rimuovi", "rm", "cancella"]):
    intent = "delete"
else:
    intent = "search"
```

## Actions

### list
Leggi `tools/cron/schedule.py` e mostra tabella di TUTTI i task (attivi e disabilitati).

### show <nome>
Mostra blocco completo di codice del task (substring match).

### add
Crea nuovo task. Interpreta input NLP per estrarre nome, comando, frequenza, orario, descrizione.

**Frequenze NLP:**
| Input utente | Metodo |
|-------------|--------|
| "ogni minuto" | `.everyMinute()` |
| "ogni 5 minuti" | `.everyFiveMinutes()` |
| "ogni 15 minuti" | `.everyFifteenMinutes()` |
| "ogni 30 minuti" / "ogni mezz'ora" | `.everyThirtyMinutes()` |
| "ogni 45 minuti" | `.everyFortyFiveMinutes()` |
| "ogni ora" / "hourly" | `.hourly()` |
| "ogni 2 ore" | `.everyTwoHours()` |
| "ogni 3 ore" | `.everyThreeHours()` |
| "ogni 6 ore" | `.everySixHours()` |
| "ogni giorno" / "daily" | `.daily()` |
| "alle 08:00" | `.dailyAt('08:00')` |
| "settimanale" | `.weekly()` |
| "mensile" | `.monthly()` |
| "solo giorni feriali" | `.weekdays()` |
| "lunedi e giovedi" | `.mondays().thursdays()` |
| "dalle 8 alle 21" | `.between('8:00', '21:00')` |

**IMPORTANTE:** Sempre aggiungere `.withoutOverlapping()` a meno che non sia esplicitamente richiesto il contrario.

### edit
Modifica task esistente (frequenza, orario, comando, finestra temporale).

### disable
Commenta il blocco con data e motivo: `# DISABLED YYYY-MM-DD: [motivo]`

### enable
Decommenta un task precedentemente disabilitato.

### delete
Rimuovi completamente il blocco. **SEMPRE chiedere conferma.**

### search
Cerca per keyword tra nomi e descrizioni.

## Metodi disponibili (Task API)

Frequenze: `everyMinute()`, `everyTwoMinutes()`, `everyFiveMinutes()`, `everyTenMinutes()`, `everyFifteenMinutes()`, `everyThirtyMinutes()`, `everyFortyFiveMinutes()`, `hourly()`, `everyTwoHours()`, `everyThreeHours()`, `everySixHours()`, `hourlyAt(minute)`, `daily()`, `dailyAt('HH:MM')`, `weekly()`, `monthly()`

Giorni: `mondays()`, `tuesdays()`, `wednesdays()`, `thursdays()`, `fridays()`, `saturdays()`, `sundays()`, `weekdays()`

Vincoli: `at('HH:MM')`, `between('HH:MM', 'HH:MM')`, `withoutOverlapping()`

## Esempi

- `/schedule` → lista tutti i task
- `/schedule show dream` → dettaglio dream-generator
- `/schedule aggiungi tmux-renamer ogni ora dalle 8 alle 23, script tools/cron/tmux-entropy-renamer.py`
- `/schedule disabilita deal-hunter-scan`
- `/schedule modifica whatsapp-status-morning alle 09:00 invece che 08:15`

## Args provided:
```
$ARGUMENTS
```
