#!/usr/bin/env python3
"""
fal.ai — Universal AI generation wrapper
Immagini, video, audio, musica, voice TTS

Usage:
    from fal_client_wrapper import generate_image, generate_video, generate_audio, tts

    # Immagini
    path = generate_image("a cyberpunk owl on a circuit board")
    path = generate_image("sunset over lake", model="recraft", aspect="16:9")

    # Video da testo
    path = generate_video("a dragon flying over mountains", duration=5)

    # Video da immagine
    path = generate_video("the dragon starts breathing fire", image_path="/tmp/dragon.png")

    # Musica
    path = generate_music("epic orchestral battle music, 30 seconds")

    # TTS
    path = tts("Buongiorno Giobi, oggi è una bella giornata.")

CLI:
    python3 fal_client_wrapper.py image "prompt here" --aspect 16:9
    python3 fal_client_wrapper.py video "prompt here" --duration 5
    python3 fal_client_wrapper.py img2video /path/to/image.png "animate this"
    python3 fal_client_wrapper.py music "jazz lounge background"
    python3 fal_client_wrapper.py tts "testo da leggere"

Required .env:
    FAL_KEY=your_fal_api_key
"""

import os
import sys
import json
import time
import requests
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Union
from dotenv import load_dotenv
import base64

BRAIN = Path(__file__).parent.parent.parent.resolve()
OUTPUT_DIR = BRAIN / 'storage' / 'fal' / 'output'

# === MODELS ===

IMAGE_MODELS = {
    "flux":       "fal-ai/flux/dev",           # qualità, veloce
    "flux-pro":   "fal-ai/flux-pro",            # qualità top
    "flux-schnell": "fal-ai/flux/schnell",      # velocissimo, 4 steps
    "recraft":    "fal-ai/recraft-v3",          # ottimo per grafica/design
    "sdxl":       "fal-ai/stable-diffusion-xl", # classico
}
DEFAULT_IMAGE = "flux"

VIDEO_MODELS = {
    "kling":      "fal-ai/kling-video/v1.6/standard/text-to-video",
    "kling-pro":  "fal-ai/kling-video/v1.6/pro/text-to-video",
    "kling-img":  "fal-ai/kling-video/v1.6/standard/image-to-video",
    "ltx":        "fal-ai/ltx-video",
    "minimax":    "fal-ai/minimax/video-01",
}
DEFAULT_VIDEO = "kling"
DEFAULT_VIDEO_IMG = "kling-img"

AUDIO_MODELS = {
    "stable-audio": "fal-ai/stable-audio",     # musica/sound effects
    "mmaudio":      "fal-ai/mmaudio/v2",       # audio per video
}

TTS_MODELS = {
    "kokoro": "fal-ai/kokoro/american-english", # veloce, buono
    "dia":    "fal-ai/dia-tts",                 # dialoghi multi-speaker
}
DEFAULT_TTS = "kokoro"

ASPECTS_IMAGE = ["square_hd", "square", "portrait_4_3", "portrait_16_9", "landscape_4_3", "landscape_16_9"]
ASPECT_MAP = {
    "1:1":   "square_hd",
    "3:4":   "portrait_4_3",
    "4:3":   "landscape_4_3",
    "9:16":  "portrait_16_9",
    "16:9":  "landscape_16_9",
}


# === UTILS ===

def _get_key(env_file: Optional[str] = None) -> str:
    if env_file:
        load_dotenv(env_file)
    else:
        brain_env = BRAIN / '.env'
        if brain_env.exists():
            load_dotenv(str(brain_env))
    key = os.getenv('FAL_KEY')
    if not key:
        raise RuntimeError("FAL_KEY not found in .env")
    return key


def _output_path(prefix: str, ext: str) -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    return str(OUTPUT_DIR / f"{ts}-{prefix}.{ext}")


def _download(url: str, output: str) -> str:
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, 'wb') as f:
        f.write(r.content)
    return output


def _run(model_id: str, inputs: dict, key: str, timeout: int = 300) -> dict:
    """Submit and poll a fal.ai job."""
    import fal_client
    os.environ['FAL_KEY'] = key

    result = fal_client.run(model_id, arguments=inputs)
    return result


# === IMAGE GENERATION ===

def generate_image(
    prompt: str,
    model: str = DEFAULT_IMAGE,
    aspect: str = "1:1",
    output: Optional[str] = None,
    negative_prompt: str = "",
    steps: int = 28,
    env_file: Optional[str] = None,
) -> str:
    """Generate an image with fal.ai.

    Args:
        prompt: Image description
        model: flux, flux-pro, flux-schnell, recraft, sdxl
        aspect: 1:1, 3:4, 4:3, 9:16, 16:9
        output: Output path (default: storage/fal/output/)
        negative_prompt: What to avoid
        steps: Inference steps
        env_file: Path to .env

    Returns:
        Path to saved image
    """
    key = _get_key(env_file)
    model_id = IMAGE_MODELS.get(model, model)
    aspect_fal = ASPECT_MAP.get(aspect, aspect)

    inputs = {
        "prompt": prompt,
        "image_size": aspect_fal,
        "num_inference_steps": steps,
        "num_images": 1,
        "enable_safety_checker": False,
    }
    if negative_prompt:
        inputs["negative_prompt"] = negative_prompt

    print(f"Generating image [{model}] — {aspect}...")
    result = _run(model_id, inputs, key)

    # Extract URL from result
    images = result.get("images") or result.get("image")
    if not images:
        raise RuntimeError(f"No images in result: {result}")

    if isinstance(images, list):
        img_url = images[0].get("url") if isinstance(images[0], dict) else images[0]
    else:
        img_url = images.get("url") if isinstance(images, dict) else images

    if not output:
        output = _output_path("img", "png")

    return _download(img_url, output)


# === VIDEO GENERATION ===

def generate_video(
    prompt: str,
    image_path: Optional[str] = None,
    model: Optional[str] = None,
    duration: int = 5,
    aspect: str = "16:9",
    output: Optional[str] = None,
    env_file: Optional[str] = None,
) -> str:
    """Generate a video from text or image.

    Args:
        prompt: Video description / motion description
        image_path: Source image for img2video (optional)
        model: kling, kling-pro, kling-img, ltx, minimax
        duration: Duration in seconds (5 or 10)
        aspect: 16:9, 9:16, 1:1
        output: Output path
        env_file: Path to .env

    Returns:
        Path to saved video (.mp4)
    """
    key = _get_key(env_file)

    # Auto-select model
    if model is None:
        model = DEFAULT_VIDEO_IMG if image_path else DEFAULT_VIDEO
    model_id = VIDEO_MODELS.get(model, model)

    inputs = {
        "prompt": prompt,
        "duration": str(duration),
        "aspect_ratio": aspect,
    }

    if image_path:
        # Convert image to data URI
        with open(image_path, 'rb') as f:
            img_data = base64.b64encode(f.read()).decode()
        ext = Path(image_path).suffix.lstrip('.') or 'png'
        inputs["image_url"] = f"data:image/{ext};base64,{img_data}"

    print(f"Generating video [{model}] — {duration}s {aspect}...")
    result = _run(model_id, inputs, key, timeout=600)

    video = result.get("video")
    if not video:
        raise RuntimeError(f"No video in result: {result}")

    video_url = video.get("url") if isinstance(video, dict) else video

    if not output:
        output = _output_path("video", "mp4")

    return _download(video_url, output)


# === MUSIC / AUDIO ===

def generate_music(
    prompt: str,
    duration: float = 30.0,
    model: str = "stable-audio",
    output: Optional[str] = None,
    env_file: Optional[str] = None,
) -> str:
    """Generate music or sound effects.

    Args:
        prompt: Music description (e.g., "epic orchestral, no vocals")
        duration: Duration in seconds (max 190 for stable-audio)
        model: stable-audio, mmaudio
        output: Output path
        env_file: Path to .env

    Returns:
        Path to saved audio (.wav or .mp3)
    """
    key = _get_key(env_file)
    model_id = AUDIO_MODELS.get(model, model)

    inputs = {
        "prompt": prompt,
        "seconds_total": duration,
    }

    print(f"Generating music [{model}] — {duration}s...")
    result = _run(model_id, inputs, key)

    audio = result.get("audio_file") or result.get("audio")
    if not audio:
        raise RuntimeError(f"No audio in result: {result}")

    audio_url = audio.get("url") if isinstance(audio, dict) else audio
    ext = "wav" if "wav" in audio_url else "mp3"

    if not output:
        output = _output_path("music", ext)

    return _download(audio_url, output)


def add_audio_to_video(
    video_path: str,
    prompt: str,
    output: Optional[str] = None,
    env_file: Optional[str] = None,
) -> str:
    """Add AI-generated audio to a video with MMAudio.

    Args:
        video_path: Path to existing video (.mp4)
        prompt: Audio description (e.g., "wind, birds, ambient forest")
        output: Output path
        env_file: Path to .env

    Returns:
        Path to saved video with audio
    """
    key = _get_key(env_file)

    with open(video_path, 'rb') as f:
        video_data = base64.b64encode(f.read()).decode()

    inputs = {
        "video_url": f"data:video/mp4;base64,{video_data}",
        "prompt": prompt,
    }

    print(f"Adding audio to video [mmaudio]...")
    result = _run(AUDIO_MODELS["mmaudio"], inputs, key)

    video = result.get("video")
    if not video:
        raise RuntimeError(f"No video in result: {result}")

    video_url = video.get("url") if isinstance(video, dict) else video

    if not output:
        output = _output_path("video-audio", "mp4")

    return _download(video_url, output)


# === TTS ===

def tts(
    text: str,
    model: str = DEFAULT_TTS,
    output: Optional[str] = None,
    env_file: Optional[str] = None,
) -> str:
    """Text-to-speech with fal.ai Kokoro.

    Args:
        text: Text to speak
        model: kokoro, dia
        output: Output path
        env_file: Path to .env

    Returns:
        Path to saved audio (.mp3)
    """
    key = _get_key(env_file)
    model_id = TTS_MODELS.get(model, model)

    inputs = {"input": text}

    print(f"TTS [{model}]...")
    result = _run(model_id, inputs, key)

    audio = result.get("audio") or result.get("audio_url")
    if not audio:
        raise RuntimeError(f"No audio in result: {result}")

    audio_url = audio.get("url") if isinstance(audio, dict) else audio

    if not output:
        output = _output_path("tts", "mp3")

    return _download(audio_url, output)


# === CLI ===

def main():
    parser = argparse.ArgumentParser(description="fal.ai — AI generation (image, video, audio, tts)")
    sub = parser.add_subparsers(dest="command")

    # Image
    img = sub.add_parser("image", aliases=["img", "i"], help="Generate image")
    img.add_argument("prompt")
    img.add_argument("--model", "-m", default=DEFAULT_IMAGE, choices=list(IMAGE_MODELS.keys()))
    img.add_argument("--aspect", "-a", default="1:1")
    img.add_argument("--output", "-o")
    img.add_argument("--steps", type=int, default=28)

    # Video
    vid = sub.add_parser("video", aliases=["vid", "v"], help="Text-to-video")
    vid.add_argument("prompt")
    vid.add_argument("--model", "-m", default=DEFAULT_VIDEO, choices=list(VIDEO_MODELS.keys()))
    vid.add_argument("--duration", "-d", type=int, default=5)
    vid.add_argument("--aspect", "-a", default="16:9")
    vid.add_argument("--output", "-o")

    # Image-to-video
    i2v = sub.add_parser("img2video", aliases=["i2v"], help="Image-to-video")
    i2v.add_argument("image_path", help="Source image path")
    i2v.add_argument("prompt", help="Motion description")
    i2v.add_argument("--model", "-m", default=DEFAULT_VIDEO_IMG)
    i2v.add_argument("--duration", "-d", type=int, default=5)
    i2v.add_argument("--output", "-o")

    # Music
    mus = sub.add_parser("music", aliases=["audio", "a"], help="Generate music/audio")
    mus.add_argument("prompt")
    mus.add_argument("--duration", "-d", type=float, default=30.0)
    mus.add_argument("--model", "-m", default="stable-audio")
    mus.add_argument("--output", "-o")

    # Add audio to video
    av = sub.add_parser("addaudio", help="Add audio to existing video")
    av.add_argument("video_path")
    av.add_argument("prompt")
    av.add_argument("--output", "-o")

    # TTS
    t = sub.add_parser("tts", aliases=["speak"], help="Text to speech")
    t.add_argument("text")
    t.add_argument("--model", "-m", default=DEFAULT_TTS)
    t.add_argument("--output", "-o")

    # Models list
    sub.add_parser("models", help="List available models")

    args = parser.parse_args()

    if args.command in ("image", "img", "i"):
        path = generate_image(args.prompt, model=args.model, aspect=args.aspect,
                              output=args.output, steps=args.steps)
        print(f"Saved: {path}")

    elif args.command in ("video", "vid", "v"):
        path = generate_video(args.prompt, model=args.model, duration=args.duration,
                              aspect=args.aspect, output=args.output)
        print(f"Saved: {path}")

    elif args.command in ("img2video", "i2v"):
        path = generate_video(args.prompt, image_path=args.image_path, model=args.model,
                              duration=args.duration, output=args.output)
        print(f"Saved: {path}")

    elif args.command in ("music", "audio", "a"):
        path = generate_music(args.prompt, duration=args.duration, model=args.model,
                              output=args.output)
        print(f"Saved: {path}")

    elif args.command == "addaudio":
        path = add_audio_to_video(args.video_path, args.prompt, output=args.output)
        print(f"Saved: {path}")

    elif args.command in ("tts", "speak"):
        path = tts(args.text, model=args.model, output=args.output)
        print(f"Saved: {path}")

    elif args.command == "models":
        print("=== IMAGE ===")
        for k, v in IMAGE_MODELS.items():
            print(f"  {k}: {v}")
        print("=== VIDEO ===")
        for k, v in VIDEO_MODELS.items():
            print(f"  {k}: {v}")
        print("=== AUDIO ===")
        for k, v in AUDIO_MODELS.items():
            print(f"  {k}: {v}")
        print("=== TTS ===")
        for k, v in TTS_MODELS.items():
            print(f"  {k}: {v}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
