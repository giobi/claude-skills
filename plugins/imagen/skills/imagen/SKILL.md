---
name: imagen
description: "AI image generation — Gemini Imagen, fal.ai (image/video/audio), Replicate Flux"
user-invocable: true
argument-hint: "[prompt] [--backend gemini|fal|flux] [--aspect 1:1|16:9|...] [--output path]"
requires:
  env:
    - GEMINI_API_KEY  # or FAL_KEY or REPLICATE_API_TOKEN
---

# /imagen — AI Image Generation

Genera immagini (e video, audio, TTS) tramite AI. Supporta 3 backend intercambiabili.

## Backend disponibili

| Backend | Skill file | Env var richiesta | Capacità |
|---------|-----------|-------------------|----------|
| **Gemini Imagen** | `imagen.py` | `GEMINI_API_KEY` | Immagini (fast/standard/ultra) |
| **fal.ai** | `fal_client_wrapper.py` | `FAL_KEY` | Immagini, video, audio, TTS, img2video |
| **Replicate Flux** | `replicate_flux.py` | `REPLICATE_API_TOKEN` | Immagini + LoRA custom |

Configura almeno uno nel `.env`. Se più backend sono disponibili, usa il default in `wiki/skills/imagen.md`.

## Setup

```
# Gemini Imagen (Google AI Studio - free tier: 1500 req/day)
GEMINI_API_KEY=your_key

# fal.ai (pay-per-use, molti modelli)
FAL_KEY=your_key

# Replicate (pay-per-use, Flux + LoRA)
REPLICATE_API_TOKEN=your_token
```

## Comandi

```
/imagen un gufo su un circuito cyberpunk
/imagen landscape at sunset --aspect 16:9
/imagen pixel art castle --backend flux
/imagen --output /path/to/file.png portrait photo
/imagen video: a dragon flying --backend fal
/imagen tts: "ciao mondo" --backend fal
/imagen music: jazz lounge background --backend fal
```

## Wrapper Python

### Gemini Imagen (immagini)

```python
import sys
sys.path.insert(0, '.claude/skills/imagen')
from imagen import generate

path = generate("owl on circuit board, cyberpunk")
path = generate("pixel art castle", model="fast", aspect="16:9")
path = generate("logo design", output="/tmp/logo.png")

# Modelli: "fast", "standard", "ultra"
# Aspect: "1:1", "3:4", "4:3", "9:16", "16:9"
```

### fal.ai (immagini, video, audio, TTS)

```python
import sys
sys.path.insert(0, '.claude/skills/imagen')
from fal_client_wrapper import generate_image, generate_video, generate_audio, tts

# Immagine
path = generate_image("a cyberpunk owl", model="recraft", aspect="16:9")

# Video da testo
path = generate_video("a dragon flying over mountains", duration=5)

# Video da immagine
path = generate_video("the dragon breathes fire", image_path="/tmp/dragon.png")

# Musica
path = generate_music("epic orchestral battle, 30 seconds")

# Text-to-speech
path = tts("Buongiorno, oggi è una bella giornata.")
```

### Replicate Flux (immagini + LoRA)

```python
import sys
sys.path.insert(0, '.claude/skills/imagen')
from replicate_flux import generate, train_lora

# Base Flux
path = generate("a cat on a keyboard")

# Con LoRA custom
path = generate("my_character at a cafe", lora="my-character")

# Allena nuovo LoRA
model_id = train_lora(
    images_dir="/path/to/reference/images",
    name="my-character",
    trigger_word="my_character"
)
```

## Intent Detection

```python
args = "$ARGUMENTS".strip()
args_lower = args.lower()

# Detect media type
if any(w in args_lower for w in ["video:", "video di", "animazione"]):
    media_type = "video"
elif any(w in args_lower for w in ["tts:", "voce:", "leggi:", "say:"]):
    media_type = "tts"
elif any(w in args_lower for w in ["music:", "musica:", "audio:"]):
    media_type = "audio"
else:
    media_type = "image"  # default

# Detect backend override
if "--backend fal" in args_lower:
    backend = "fal"
elif "--backend flux" in args_lower or "--backend replicate" in args_lower:
    backend = "flux"
elif "--backend gemini" in args_lower:
    backend = "gemini"
else:
    backend = None  # usa default da wiki/skills/imagen.md o primo disponibile

# Parse aspect
import re
aspect_match = re.search(r'--aspect (\S+)', args)
aspect = aspect_match.group(1) if aspect_match else "1:1"

# Parse output path
output_match = re.search(r'--output (\S+)', args)
output = output_match.group(1) if output_match else None

# Clean prompt
prompt = re.sub(r'--\w+ \S+', '', args).strip()
```

## Default Backend Logic

```python
import os
if backend is None:
    if os.getenv('FAL_KEY'):
        backend = "fal"
    elif os.getenv('GEMINI_API_KEY'):
        backend = "gemini"
    elif os.getenv('REPLICATE_API_TOKEN'):
        backend = "flux"
    else:
        raise ValueError("Nessun backend configurato. Aggiungi FAL_KEY, GEMINI_API_KEY o REPLICATE_API_TOKEN al .env")
```
