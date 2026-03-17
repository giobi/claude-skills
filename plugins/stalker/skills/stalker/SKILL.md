---
name: stalker
description: "Stalker — Ricerca approfondita su qualsiasi soggetto (persone, aziende, domini, oggetti, concetti)"
argument-hint: "[soggetto] [livello 1-10] [contesto/materiale]"
disable-model-invocation: true
---

**Stalker** — Trova tutto su qualsiasi cosa

**Input**: `$ARGUMENTS`

## Cosa e Stalker

OSINT e ricerca approfondita su qualsiasi soggetto. Dai un nome, un handle, una foto, un concetto — Stalker scava e ti porta tutto quello che trova.

**Funziona su TUTTO:**
- Persone (nome, handle social, foto)
- Aziende (nome, dominio, P.IVA)
- Domini/siti web
- Oggetti (auto, dispositivi, prodotti)
- Animali (razze, esemplari specifici)
- Concetti/topic (ricerca approfondita, stato dell'arte)

## Livelli di profondita

| Livello | Nome | Tempo | Cosa fa |
|---------|------|-------|---------|
| 1-3 | **Quick** | 2-3 min | Google prima pagina, social pubblici (IG, FB, LinkedIn), sito web principale |
| 4-6 | **Medium** | 4-6 min | + articoli, menzioni, domini collegati, WHOIS, tech stack, recensioni, GitHub, cross-reference |
| 7-9 | **Deep** | 7-9 min | + archivi web, registri pubblici, connessioni tra entita, timeline attivita, foto taggate, PEC/visure |
| 10 | **Stalker** | 10 min | Tutto. Ogni fonte disponibile, cross-reference multipli, ricostruzione timeline completa |

**Timeout massimo: 10 minuti.** Dopo 10 minuti, report con quello che hai trovato.

**Regola di uscita anticipata:** se al livello richiesto hai gia raccolto abbastanza info (soggetto ben coperto, nessuna fonte nuova), puoi chiudere prima.

## Step 0: Parse input

### Parsing NLP

L'input e linguaggio naturale. Esempi:

```
/stalker Mario Rossi 7 lavora in una web agency a Milano
/stalker @marietto_dev 5
/stalker nexum srl 4
/stalker tesla model 3 2024 6
/stalker border collie 3
/stalker cos'e il protocollo QUIC 2
```

**Estrai:**
1. **Soggetto**: il target della ricerca
2. **Livello**: numero 1-10 (default: 5 se non specificato)
3. **Contesto**: tutto il resto — info aggiuntive, materiale, indizi

### Detect tipo soggetto

```python
if soggetto starts with "@":
    tipo = "social_profile"
elif soggetto looks like domain/URL:
    tipo = "domain"
elif soggetto contains "srl|spa|snc|sas|ltd|inc|gmbh":
    tipo = "company"
elif soggetto is a known concept/topic:
    tipo = "concept"
elif soggetto matches object patterns (targa, modello, marca):
    tipo = "object"
else:
    tipo = "person"  # default
```

## Step 1: Piano di ricerca

In base al tipo e livello, costruisci un piano. **NON chiedere conferma** — parti subito.

### Fonti per tipo

**Persona:**
| Livello | Fonti |
|---------|-------|
| 1-3 | Google, social pubblici (IG, FB), **`/linkedin`** per profilo base |
| 4-6 | + Google Images, GitHub, articoli, WHOIS. **`/linkedin`** con filtri company/location |
| 7-10 | + archivio web, PEC, albi. **`/linkedin`** con Proxycurl se disponibile |

**Azienda:**
| Livello | Fonti |
|---------|-------|
| 1-3 | Google, sito ufficiale, social, Google Maps |
| 4-6 | + WHOIS, tech stack, **`/linkedin`** per dipendenti, fatturato stimato |
| 7-10 | + visura CCIAA, PEC, ATECO, partecipazioni, brevetti |

**Dominio:**
| Livello | Fonti |
|---------|-------|
| 1-3 | WHOIS, homepage, DNS |
| 4-6 | + tech stack, SEO, backlinks, hosting |
| 7-10 | + Wayback Machine, certificati SSL, sottodomini |

## Step 2: Esecuzione — Metodo a spirale

**NON raccogliere tutto e poi analizzare.** Lavora a cicli iterativi:

```
CICLO N (1 minuto):
  1. RACCOGLI — cerca con query mirate
  2. DEDUCI — cosa implica quello che hai trovato?
  3. IPOTESI — formula ipotesi verificabili
  4. QUERY NEXT — costruisci le ricerche del ciclo successivo
  → ripeti fino a livello raggiunto o timeout
```

### Skill usate durante la ricerca

- **`/linkedin`** — per tutto cio che riguarda LinkedIn (profili, aziende, dipendenti)
- **WebSearch** — ricerche Google
- **WebFetch** — scavare nelle pagine trovate
- **Playwright** — screenshot profili (livello 7+), Instagram (se credenziali disponibili)

### Regole di esecuzione

1. **Parallelizza** le ricerche quando possibile
2. **Cross-reference**: ogni info, cerca conferma da seconda fonte
3. **Non inventare**: se non trovi, scrivi "non trovato"
4. **Ogni ciclo ~1 minuto** — poi fermati, deduci, ripeti
5. **Query successive basate su deduzioni** — non generiche

## Step 3: Analisi Visiva (livello 4+)

Cerca SEMPRE immagini per persone e aziende. **Target: 3-10 foto per report.**

### Download e analisi foto

1. **Scarica** in `public/stalker/{slug}/photos/`
2. **Verifica** con `file` (anti-hotlink = HTML, non JPEG)
3. **Estrai EXIF** con `identify -verbose` o `exiftool`
4. **Analizza visivamente** con Read tool (multimodale)
5. **Cross-reference**: stessa foto su piu piattaforme?

### Layout foto nel report HTML — 3 zone

1. **Cover hero** — full-width in cima, `object-fit: cover`, gradient fade
2. **Profile pic** — 120px circolare, bordo accent, sovrapposta alla cover
3. **Gallery** — griglia 3 colonne con card `.wide` e `.tall`, lightbox CSS-only

## Step 3c: Deduzione Finale

Non elencare dati — **collega i punti**. Ogni fatto da solo e un punto; il valore dello stalker e disegnare le linee tra i punti.

### Cosa deve contenere

```
RICOSTRUZIONE NARRATIVA:
  Chi e questa persona DAVVERO (non chi dice di essere)
  Come vive, dove si muove, con chi sta
  Cosa nasconde (e PERCHE)

PREDIZIONI VERIFICABILI:
  Basate sui pattern trovati

LIVELLO DI OPACITA:
  Quanto e facile/difficile trovare questa persona e perche
```

## Step 4: Output

### 4a. Report HTML (SEMPRE)

In `public/stalker/{slug}/index.html` — dark theme, scanlines, accent verde, JetBrains Mono.

### 4b. Report in chat

```
🔍 **Stalker: {soggetto}** — Livello {N}/10

{riassunto discorsivo}

📄 Report: public/stalker/{slug}/
**Fonti:** {N} | **Confidence:** {alta/media/bassa} | **Tempo:** {N} min
```

### 4c. Salvataggio nel brain

Per persone/aziende, chiedi se salvare in `wiki/people/` o `wiki/companies/` via brain_writer.

## Regole

1. **Niente dati inventati**
2. **Privacy**: info PUBBLICHE only
3. **SOLO OSINT** — MAI usare dati dal brain (wiki/, diary/, boot/)
4. **Rate limiting**: rispetta i tempi
5. **Timeout 10 min**
6. **Cross-reference**: almeno 2 fonti per dato importante

## Tmux

```bash
~/.tmux/set-pane-title.sh "🔍 stalker / {soggetto}"
```
