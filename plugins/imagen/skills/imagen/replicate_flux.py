#!/usr/bin/env python3
"""
Replicate Flux — Image generation with optional LoRA character consistency.

Generic wrapper. Knows nothing about Instagram, owls, or anything specific.
Any project can use this to generate images via Flux, with or without a custom LoRA.

Usage:
    from replicate_flux import generate, train_lora, list_models

    # Basic Flux generation (no LoRA)
    path = generate("a cat sitting on a keyboard")

    # With a trained LoRA
    path = generate("anacleto_owl at a cafe", lora="anacleto-owl")

    # Train a new LoRA
    model_id = train_lora(
        images_dir="/path/to/reference/images",
        name="my-character",
        trigger_word="my_character_trigger"
    )

CLI:
    python3 replicate_flux.py generate "prompt here" --lora anacleto-owl
    python3 replicate_flux.py generate "a sunset" --aspect 16:9
    python3 replicate_flux.py train /path/to/images my-model my_trigger
    python3 replicate_flux.py models
    python3 replicate_flux.py status <training_id>

Required .env:
    REPLICATE_API_TOKEN=r8_...
"""

import os
import sys
import json
import time
import zipfile
import tempfile
import requests
import argparse
import base64
from pathlib import Path
from datetime import datetime
from typing import Optional, Union, List, Dict, Any
from dotenv import load_dotenv

BRAIN = Path(__file__).parent.parent.parent.resolve()
MODELS_FILE = BRAIN / 'storage' / 'replicate' / 'models.json'
OUTPUT_DIR = BRAIN / 'storage' / 'replicate' / 'output'

API_BASE = "https://api.replicate.com/v1"

# Flux models on Replicate
FLUX_MODEL = "black-forest-labs/flux-dev"
FLUX_LORA_MODEL = "lucataco/flux-dev-lora"
FLUX_TRAINER = "ostris/flux-dev-lora-trainer"
FAST_TRAINER = "replicate/fast-flux-trainer"

ASPECTS = ["1:1", "3:4", "4:3", "9:16", "16:9"]


def _get_token(env_file: Optional[str] = None) -> str:
    """Get Replicate API token from environment."""
    if env_file:
        load_dotenv(env_file)
    else:
        # Try brain .env first, then walk up
        brain_env = BRAIN / '.env'
        if brain_env.exists():
            load_dotenv(str(brain_env))
        else:
            current = Path.cwd()
            for parent in [current] + list(current.parents):
                env_path = parent / ".env"
                if env_path.exists():
                    load_dotenv(str(env_path))
                    break

    token = os.getenv('REPLICATE_API_TOKEN')
    if not token:
        raise RuntimeError(
            "REPLICATE_API_TOKEN not found in environment.\n"
            "Get your token at: https://replicate.com/account/api-tokens"
        )
    return token


def _api(method: str, path: str, token: str, data: dict = None, timeout: int = 30) -> dict:
    """Make an API call to Replicate."""
    url = f"{API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    if method == "GET":
        r = requests.get(url, headers=headers, timeout=timeout)
    elif method == "POST":
        r = requests.post(url, headers=headers, json=data, timeout=timeout)
    else:
        raise ValueError(f"Unsupported method: {method}")

    if r.status_code >= 400:
        raise RuntimeError(f"Replicate API error ({r.status_code}): {r.text[:500]}")

    return r.json()


def _load_models() -> dict:
    """Load the registry of trained LoRA models."""
    if MODELS_FILE.exists():
        try:
            return json.loads(MODELS_FILE.read_text())
        except:
            pass
    return {}


def _save_models(models: dict):
    """Save the model registry."""
    MODELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    MODELS_FILE.write_text(json.dumps(models, indent=2, ensure_ascii=False))


def _resolve_lora(lora: str) -> dict:
    """Resolve a LoRA name to model_id and trigger_word.

    Args:
        lora: Either a local name from models.json, or a full replicate model path.

    Returns:
        dict with model_id and trigger_word
    """
    models = _load_models()

    # Check local registry first
    if lora in models:
        return models[lora]

    # Assume it's a full replicate model path (user/model:version or user/model)
    return {"model_id": lora, "trigger_word": None}


# === GENERATION ===

def generate(
    prompt: str,
    lora: Optional[str] = None,
    aspect: str = "3:4",
    output: Optional[str] = None,
    guidance: float = 3.5,
    steps: int = 28,
    lora_scale: float = 1.0,
    env_file: Optional[str] = None,
) -> str:
    """Generate an image with Flux, optionally using a LoRA model.

    Args:
        prompt: Image description. Include the trigger word if using a LoRA.
        lora: Name from models.json or full replicate model path. None for base Flux.
        aspect: Aspect ratio (1:1, 3:4, 4:3, 9:16, 16:9)
        output: Output file path. Default: storage/replicate/output/{timestamp}.png
        guidance: Guidance scale (default 3.5)
        steps: Number of inference steps (default 28)
        lora_scale: LoRA strength 0.0-2.0 (default 1.0)
        env_file: Path to .env file

    Returns:
        Path to saved image file.
    """
    token = _get_token(env_file)

    if aspect not in ASPECTS:
        raise ValueError(f"Invalid aspect: {aspect}. Use: {ASPECTS}")

    # Build input parameters
    input_params = {
        "prompt": prompt,
        "aspect_ratio": aspect,
        "guidance_scale": guidance,
        "num_inference_steps": steps,
        "output_format": "png",
        "output_quality": 90,
    }

    if lora:
        lora_info = _resolve_lora(lora)
        model_id = lora_info["model_id"]

        # If trigger word exists and not already in prompt, prepend it
        trigger = lora_info.get("trigger_word")
        if trigger and trigger not in prompt:
            input_params["prompt"] = f"{trigger} {prompt}"

        input_params["hf_lora"] = model_id
        input_params["lora_scale"] = lora_scale

        # Use the Flux LoRA runner
        prediction_model = FLUX_LORA_MODEL
    else:
        prediction_model = FLUX_MODEL

    # Create prediction
    data = {
        "input": input_params,
    }

    # Use the predictions endpoint with model version
    result = _api("POST", f"/models/{prediction_model}/predictions", token, data)

    # Poll for completion
    prediction_url = result.get("urls", {}).get("get", "")
    if not prediction_url:
        prediction_id = result.get("id")
        prediction_url = f"{API_BASE}/predictions/{prediction_id}"
    else:
        # URL is absolute, extract path
        prediction_id = result.get("id")

    status = result.get("status")
    max_wait = 300  # 5 min max
    waited = 0

    while status not in ("succeeded", "failed", "canceled"):
        time.sleep(3)
        waited += 3
        if waited > max_wait:
            raise RuntimeError(f"Prediction timed out after {max_wait}s")

        poll = _api("GET", f"/predictions/{prediction_id}", token)
        status = poll.get("status")
        result = poll

    if status != "succeeded":
        error = result.get("error", "Unknown error")
        raise RuntimeError(f"Prediction failed: {error}")

    # Get output URL(s)
    output_urls = result.get("output")
    if not output_urls:
        raise RuntimeError("No output in prediction result")

    if isinstance(output_urls, list):
        image_url = output_urls[0]
    else:
        image_url = output_urls

    # Download image
    if not output:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        lora_suffix = f"-{lora}" if lora else ""
        output = str(OUTPUT_DIR / f'{timestamp}{lora_suffix}.png')

    img_response = requests.get(image_url, timeout=60)
    img_response.raise_for_status()

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, 'wb') as f:
        f.write(img_response.content)

    return output


# === TRAINING ===

def train_lora(
    images_dir: str,
    name: str,
    trigger_word: str,
    steps: int = 1000,
    fast: bool = True,
    env_file: Optional[str] = None,
) -> Dict[str, Any]:
    """Train a Flux LoRA model on Replicate.

    Args:
        images_dir: Directory containing reference images (jpg/png)
        name: Model name (will be created as your-username/name on Replicate)
        trigger_word: Unique trigger word for the character (e.g., "anacleto_owl")
        steps: Training steps (default 1000, fast trainer default varies)
        fast: Use fast trainer (under 2 min, under $2) vs standard
        env_file: Path to .env file

    Returns:
        dict with training_id, status, model_id
    """
    token = _get_token(env_file)

    images_path = Path(images_dir)
    if not images_path.exists():
        raise ValueError(f"Images directory not found: {images_dir}")

    # Collect images
    image_files = []
    for ext in ('*.png', '*.jpg', '*.jpeg', '*.webp'):
        image_files.extend(images_path.glob(ext))

    if len(image_files) < 5:
        raise ValueError(f"Need at least 5 images, found {len(image_files)}")

    print(f"Found {len(image_files)} images for training")

    # Create zip file
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
        zip_path = tmp.name

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for img in image_files:
            zf.write(img, img.name)

    print(f"Created training zip: {zip_path} ({Path(zip_path).stat().st_size / 1024:.0f}KB)")

    try:
        # Upload zip to Replicate via their file upload API
        with open(zip_path, 'rb') as f:
            upload_resp = requests.post(
                f"{API_BASE}/files",
                headers={
                    "Authorization": f"Bearer {token}",
                },
                files={"content": (f"{name}-training.zip", f, "application/zip")},
                timeout=120,
            )

        if upload_resp.status_code >= 400:
            raise RuntimeError(f"File upload failed: {upload_resp.text[:300]}")

        file_url = upload_resp.json().get("urls", {}).get("get", "")
        if not file_url:
            # Try direct URL
            file_url = upload_resp.json().get("url", "")

        if not file_url:
            raise RuntimeError(f"No URL in upload response: {upload_resp.json()}")

        print(f"Uploaded training data: {file_url[:80]}...")

        # Get Replicate username
        user_resp = _api("GET", "/account", token)
        username = user_resp.get("username")
        if not username:
            raise RuntimeError("Could not get Replicate username")

        # Create the destination model first
        destination = f"{username}/{name}"
        try:
            _api("POST", "/models", token, {
                "owner": username,
                "name": name,
                "visibility": "private",
                "hardware": "gpu-t4",
            })
            print(f"Created model: {destination}")
        except RuntimeError as e:
            if "already exists" in str(e).lower():
                print(f"Model {destination} already exists, reusing")
            else:
                raise

        # Pick trainer
        trainer = FAST_TRAINER if fast else FLUX_TRAINER

        # Get latest version of trainer
        trainer_resp = _api("GET", f"/models/{trainer}", token)
        trainer_version = trainer_resp.get("latest_version", {}).get("id")
        if not trainer_version:
            raise RuntimeError(f"Could not get trainer version for {trainer}")

        # Start training
        training_data = {
            "destination": destination,
            "input": {
                "input_images": file_url,
                "trigger_word": trigger_word,
                "steps": steps,
            }
        }

        result = _api(
            "POST",
            f"/models/{trainer}/versions/{trainer_version}/trainings",
            token,
            training_data
        )

        training_id = result.get("id")
        print(f"Training started: {training_id}")
        print(f"Destination: {destination}")
        print(f"Trigger word: {trigger_word}")

        # Save to registry immediately (status: training)
        models = _load_models()
        models[name] = {
            "model_id": destination,
            "trigger_word": trigger_word,
            "training_id": training_id,
            "status": "training",
            "started_at": datetime.now().isoformat(),
            "images_count": len(image_files),
            "steps": steps,
            "trainer": "fast" if fast else "standard",
        }
        _save_models(models)

        return {
            "training_id": training_id,
            "status": "training",
            "model_id": destination,
            "trigger_word": trigger_word,
        }

    finally:
        # Cleanup temp zip
        try:
            os.unlink(zip_path)
        except:
            pass


def check_training(training_id: str, env_file: Optional[str] = None) -> Dict[str, Any]:
    """Check status of a training job.

    Returns dict with status, logs, and version if completed.
    """
    token = _get_token(env_file)
    result = _api("GET", f"/trainings/{training_id}", token)

    status = result.get("status")
    info = {
        "training_id": training_id,
        "status": status,
        "logs": (result.get("logs") or "")[-500:],  # Last 500 chars
    }

    if status == "succeeded":
        version = result.get("output", {}).get("version", "")
        weights = result.get("output", {}).get("weights", "")
        info["version"] = version
        info["weights_url"] = weights

        # Update model registry with version
        models = _load_models()
        for name, model in models.items():
            if model.get("training_id") == training_id:
                model["status"] = "ready"
                model["version"] = version
                model["weights_url"] = weights
                model["completed_at"] = datetime.now().isoformat()
                # Update model_id with version for direct use
                if version:
                    model["model_id"] = f"{model['model_id']}:{version}"
                break
        _save_models(models)

    elif status == "failed":
        info["error"] = result.get("error", "Unknown error")

        # Update registry
        models = _load_models()
        for name, model in models.items():
            if model.get("training_id") == training_id:
                model["status"] = "failed"
                model["error"] = info["error"]
                break
        _save_models(models)

    return info


def wait_for_training(training_id: str, env_file: Optional[str] = None, timeout: int = 1800) -> Dict[str, Any]:
    """Wait for a training to complete. Polls every 30 seconds.

    Args:
        training_id: The training ID to monitor
        timeout: Max seconds to wait (default 30 min)

    Returns:
        Final training status dict
    """
    waited = 0
    while waited < timeout:
        info = check_training(training_id, env_file)
        status = info["status"]

        if status in ("succeeded", "failed", "canceled"):
            return info

        print(f"[{waited}s] Training status: {status}...")
        time.sleep(30)
        waited += 30

    raise RuntimeError(f"Training timed out after {timeout}s")


def list_models() -> Dict[str, Any]:
    """List all trained LoRA models from the local registry."""
    return _load_models()


# === CLI ===

def main():
    parser = argparse.ArgumentParser(description="Replicate Flux — Image generation + LoRA training")
    sub = parser.add_subparsers(dest="command")

    # Generate
    gen = sub.add_parser("generate", aliases=["gen", "g"], help="Generate an image")
    gen.add_argument("prompt", help="Image description")
    gen.add_argument("--lora", "-l", help="LoRA model name or replicate path")
    gen.add_argument("--aspect", "-a", default="3:4", choices=ASPECTS)
    gen.add_argument("--output", "-o", help="Output file path")
    gen.add_argument("--guidance", type=float, default=3.5)
    gen.add_argument("--steps", type=int, default=28)
    gen.add_argument("--lora-scale", type=float, default=1.0)

    # Train
    tr = sub.add_parser("train", aliases=["t"], help="Train a LoRA model")
    tr.add_argument("images_dir", help="Directory with reference images")
    tr.add_argument("name", help="Model name")
    tr.add_argument("trigger_word", help="Trigger word for the character")
    tr.add_argument("--steps", type=int, default=1000)
    tr.add_argument("--fast", action="store_true", default=True, help="Use fast trainer")
    tr.add_argument("--standard", action="store_true", help="Use standard trainer (slower, more control)")
    tr.add_argument("--wait", action="store_true", help="Wait for training to complete")

    # Status
    st = sub.add_parser("status", aliases=["s"], help="Check training status")
    st.add_argument("training_id", help="Training ID")

    # Models
    sub.add_parser("models", aliases=["m"], help="List trained models")

    args = parser.parse_args()

    if args.command in ("generate", "gen", "g"):
        print(f"Generating image...")
        path = generate(
            prompt=args.prompt,
            lora=args.lora,
            aspect=args.aspect,
            output=args.output,
            guidance=args.guidance,
            steps=args.steps,
            lora_scale=args.lora_scale,
        )
        print(f"Saved: {path}")

    elif args.command in ("train", "t"):
        fast = not args.standard
        result = train_lora(
            images_dir=args.images_dir,
            name=args.name,
            trigger_word=args.trigger_word,
            steps=args.steps,
            fast=fast,
        )
        print(json.dumps(result, indent=2))

        if args.wait:
            print("\nWaiting for training to complete...")
            final = wait_for_training(result["training_id"])
            print(json.dumps(final, indent=2))

    elif args.command in ("status", "s"):
        info = check_training(args.training_id)
        print(json.dumps(info, indent=2))

    elif args.command in ("models", "m"):
        models = list_models()
        if not models:
            print("No models trained yet.")
        else:
            for name, info in models.items():
                status = info.get("status", "?")
                trigger = info.get("trigger_word", "?")
                print(f"  {name}: status={status}, trigger='{trigger}', model={info.get('model_id', '?')}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
