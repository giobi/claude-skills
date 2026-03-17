---
name: scar
description: "S.C.A.R. - Documenta incident/bug con Signal, Cause, Action, Reinforcement"
---

# S.C.A.R. — Signal, Cause, Action, Reinforcement

**Input**: `$ARGUMENTS`

Ogni problema lascia una cicatrice nel sistema — e quella cicatrice lo rende piu forte.

## Comportamento

Guida l'utente attraverso il processo SCAR per documentare un incident o un bug fix. Il risultato e un file strutturato che previene il ripetersi del problema.

## Workflow

### 1. Capire cosa e successo

Se `$ARGUMENTS` contiene una descrizione del problema, usala. Altrimenti chiedi:
- **Cosa hai visto?** (il Signal — il sintomo osservabile)
- **Su quale progetto?** (per sapere dove salvare)

### 2. Cercare incident esistenti (PRIMA di creare)

**SEMPRE** cercare prima se esiste gia un incident correlato:

```bash
# Cerca in incidents/ del progetto
grep -ril "keyword" wiki/projects/{progetto}/incidents/ 2>/dev/null
# Cerca in wiki/tech/ per pattern noti
grep -ril "keyword" wiki/tech/ 2>/dev/null
```

**Se trovi un incident simile:**
- NON creare un nuovo file
- Analizza: e lo stesso problema in una declinazione diversa? Una variante? Una regressione?
- Aggiorna l'incident esistente aggiungendo una sezione `## Recurrence: YYYY-MM-DD` con:
  - Il nuovo Signal (come si e manifestato questa volta)
  - Cosa e cambiato nella Cause (stesso root cause o variante?)
  - Action aggiuntiva
  - Reinforcement rafforzato — se si e ripresentato, il Reinforcement precedente non era abbastanza forte
- Se il Reinforcement precedente ha fallito, **escalalo**: documentazione → guardrail nel codice → test automatico

**L'obiettivo e identificare punti deboli**, non accumulare file. Un incident che si ripresenta in forme diverse rivela una fragilita strutturale — e quella va affrontata come tale, non come N problemi separati.

### 3. Analisi — i 4 step

Guida attraverso ogni fase:

#### S — Signal
Il sintomo grezzo, osservabile. Non l'interpretazione.
> "WebSSH lancia come utente sbagliato"

#### C — Cause
Root cause. Usa i 5 Whys: chiedi "perche?" finche non arrivi a qualcosa prevenibile.
> "OwnershipCheck auto-fix → chown errato → stat() legge owner sbagliato"

#### A — Action
Il fix concreto. Codice, config, comandi. Riproducibile.
> "Aggiunto guardrail per brain esterni in OwnershipCheck"

#### R — Reinforcement
Come previeni che si ripeta. Almeno UNO tra:
- Test automatico
- Guardrail nel codice
- Documentazione
- Regola operativa

### 4. Classificare

Chiedi: **Bug o Incident?**

| | Bug | Incident |
|---|-----|----------|
| **Impatto** | Potenziale | Reale, gia successo |
| **Urgenza** | Puo aspettare | Azione immediata |

### 5. Salvare

In base al tipo e gravita:

**Incident grave (NUOVO)** → crea file in `wiki/projects/{progetto}/incidents/YYYY-MM-DD-slug.md`

```markdown
---
date: 'YYYY-MM-DD'
type: incident
severity: critical|high|medium|low
tags:
  - incident
  - {progetto}
  - scar
---

# Incident: {titolo}

## Signal
{cosa e stato osservato}

## Cause
{root cause analysis}

## Action
{fix applicati}

## Reinforcement
{prevenzione futura}
```

**Incident che si ripete (RECURRENCE)** → aggiorna il file esistente aggiungendo:

```markdown
## Recurrence: YYYY-MM-DD

### Signal
{come si e manifestato questa volta — stessa cosa o variante?}

### Cause
{stesso root cause o causa diversa che porta allo stesso sintomo?}

### Action
{fix aggiuntivo}

### Reinforcement (escalation)
{il Reinforcement precedente non bastava — cosa si aggiunge?}
Escalation: {documentazione → guardrail → test automatico}
```

**Regola di escalation:** se un incident si ripresenta, il Reinforcement precedente era troppo debole. Scala di un livello: regola operativa → documentazione → guardrail nel codice → test automatico. Se era gia test automatico e si e ripresentato, il test non copriva il caso — estendilo.

**Bug fix** → commit message strutturato + commento nel codice se necessario

**Pattern ricorrente** → aggiorna `wiki/tech/` o `wiki/patterns/`

### 6. Azioni automatiche

Dopo aver documentato:
1. Se c'e un Reinforcement di tipo "regola" → aggiungilo alla documentazione
2. Se c'e un Reinforcement di tipo "test" → suggerisci il test da scrivere
3. Aggiorna il progetto index.md con riferimento all'incident
4. Se grave → suggerisci notifica (Discord/email)
5. Se recurrence → segnala esplicitamente che il punto debole e strutturale

## Riferimento

Documentazione completa del protocollo: `wiki/tech/scar.md`

## Esempi d'uso

- `/scar webssh lancia come utente sbagliato` → guida attraverso i 4 step
- `/scar` → chiede cosa e successo e guida da li
- `/scar bug il parsing della data non gestisce epoch ms` → documenta come bug
- `/scar di nuovo ownership sbagliato su brain esterno` → trova incident esistente, aggiunge Recurrence con escalation del Reinforcement
