#!/usr/bin/env python3
"""
Imagen 4.0 - Google image generation via Gemini API

Usage:
    from imagen import generate

    # Basic
    path = generate("owl on circuit board, cyberpunk")

    # With options
    path = generate(
        prompt="pixel art castle",
        model="fast",           # fast, standard, ultra
        aspect="16:9",          # 1:1, 3:4, 4:3, 9:16, 16:9
        output="/tmp/castle.png"
    )

    # Multi-tenant (ABChat)
    path = generate("logo design", env_file="/var/abchat/workspaces/user/.env")

CLI:
    python3 imagen.py "owl cyberpunk" --aspect 16:9 --output /tmp/owl.png

Required .env keys:
    GEMINI_API_KEY=your_gemini_api_key

Pricing (Free tier):
    - 1500 requests/day total (shared with Gemini text)
    - Imagen generations count toward this limit
    - Recommended: track usage to stay within limits
"""

import os
import sys
import base64
import requests
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Union, List
from dotenv import load_dotenv


def find_env_file() -> Optional[str]:
    """Find .env file from current directory upwards."""
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        env_path = parent / ".env"
        if env_path.exists():
            return str(env_path)
    return None

MODELS = {
    "fast": "imagen-4.0-fast-generate-001",
    "standard": "imagen-4.0-generate-001",
    "ultra": "imagen-4.0-ultra-generate-001",
}

ASPECTS = ["1:1", "3:4", "4:3", "9:16", "16:9"]


def generate(
    prompt: str,
    model: str = "standard",
    aspect: str = "1:1",
    output: Optional[str] = None,
    count: int = 1,
    env_file: Optional[str] = None
) -> Union[str, List[str]]:
    """
    Generate image with Imagen 4.0.

    Args:
        prompt: Image description
        model: fast, standard, ultra (default: standard)
        aspect: 1:1, 3:4, 4:3, 9:16, 16:9 (default: 1:1)
        output: Output path (default: /tmp/imagen-{timestamp}.png)
        count: Number of images (1-4)
        env_file: Path to .env file (for multi-tenant usage)

    Returns:
        Path to generated image (str) or list of paths if count > 1

    Raises:
        ValueError: Invalid parameters
        RuntimeError: API error or missing GEMINI_API_KEY
    """
    if not env_file:
        env_file = find_env_file()

    if env_file:
        load_dotenv(env_file)

    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not found in environment.\n"
            f"Env file: {env_file or 'not found'}\n"
            "Get free API key: https://aistudio.google.com/app/apikey"
        )

    # Validate
    if model not in MODELS:
        raise ValueError(f"Invalid model: {model}. Use: {list(MODELS.keys())}")
    if aspect not in ASPECTS:
        raise ValueError(f"Invalid aspect: {aspect}. Use: {ASPECTS}")
    if not 1 <= count <= 4:
        raise ValueError("count must be 1-4")

    model_id = MODELS[model]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:predict?key={api_key}"

    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": count,
            "aspectRatio": aspect,
        }
    }

    response = requests.post(url, json=payload, timeout=120)
    result = response.json()

    if response.status_code != 200:
        error = result.get('error', {}).get('message', str(result))
        raise RuntimeError(f"Imagen API error: {error}")

    if 'predictions' not in result:
        raise RuntimeError(f"No predictions in response: {result}")

    # Save image(s)
    paths = []
    for i, pred in enumerate(result['predictions']):
        img_data = pred.get('bytesBase64Encoded')
        if not img_data:
            continue

        if output and count == 1:
            out_path = output
        elif output:
            base = Path(output)
            out_path = str(base.parent / f"{base.stem}-{i+1}{base.suffix}")
        else:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            suffix = f"-{i+1}" if count > 1 else ""
            out_path = f"/tmp/imagen-{timestamp}{suffix}.png"

        with open(out_path, 'wb') as f:
            f.write(base64.b64decode(img_data))
        paths.append(out_path)

    return paths[0] if count == 1 else paths


def main():
    parser = argparse.ArgumentParser(description="Generate images with Imagen 4.0")
    parser.add_argument("prompt", help="Image description")
    parser.add_argument("-m", "--model", default="standard", choices=MODELS.keys(),
                        help="Model: fast, standard, ultra")
    parser.add_argument("-a", "--aspect", default="1:1", choices=ASPECTS,
                        help="Aspect ratio")
    parser.add_argument("-o", "--output", help="Output path")
    parser.add_argument("-n", "--count", type=int, default=1, choices=[1,2,3,4],
                        help="Number of images")

    args = parser.parse_args()

    try:
        result = generate(
            prompt=args.prompt,
            model=args.model,
            aspect=args.aspect,
            output=args.output,
            count=args.count
        )
        if isinstance(result, list):
            for p in result:
                print(f"✅ {p}")
        else:
            print(f"✅ {result}")
    except Exception as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
