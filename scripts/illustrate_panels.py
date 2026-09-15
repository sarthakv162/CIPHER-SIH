#!/usr/bin/env python3
"""Generate one illustrated PNG panel per scene from an existing video_package storyboard.json.

This is a **standalone, optional** script. It is deliberately outside the Rupantar pipeline:
not a `ModelManager` slot, not a runtime, not an entry in `configs/models.yaml`, never invoked
by `scripts/fetch_models.sh` or application code, and **not checked by `selfcheck`**. Do not
"fix" that by wiring it in later without an explicit instruction — see PLAN.md Phase 9d.

What it does
------------
Reads a `storyboard.json` written by `rupantar.render.video_render`, pairs each scene (in
`data["scenes"]`, original order) with the filename of the non-extra panel PNG that
`render_video`/`_write_panels` will read for it (`data["panels"]`, filtered to
`is_extra == false`, in file order — extra panels such as the infographic hero/chart are
spliced in after the first scene and are never touched by this script), builds one short
text-to-image prompt per scene from its `visual_recommendation` (+ `scene_description` for
context), and renders each with a local few-step diffusion pipeline. Every output file is
named exactly `panel_{index:02d}.png` in `--out`, matching what `render_video` already expects
(via `render/video_render.py:_write_panels`'s illustrated-mode check) so nothing on the reading
side needs to change to pick these up. Set `GenerationParams.video_style: illustrated` on the
transform so the pipeline actually uses them instead of the composed renderer.

One-time model fetch (run ONCE, online, before air-gapping — never called by this script or
by any application code):

    pip install "huggingface_hub[cli]"   # if not already available
    python -c "
from huggingface_hub import snapshot_download
snapshot_download(repo_id='stabilityai/sdxl-turbo', local_dir='models/imagegen')
"

Expected directory layout under `models/imagegen/` (the diffusers snapshot layout, as
`snapshot_download` writes it — this is the SDXL-Turbo repo's own structure, not a Rupantar
convention):

    models/imagegen/
        model_index.json
        unet/...
        vae/...
        text_encoder/...
        text_encoder_2/...
        tokenizer/...
        tokenizer_2/...
        scheduler/...

If `models/imagegen/` has no usable model files (missing, or no `model_index.json`), this
script prints a clear error to stderr, exits non-zero, and writes nothing — no partial output
directory.

`--steps` default and why: SDXL-Turbo's own model card documents 1-4 step "real-time" sampling
with `guidance_scale=0.0` (no classifier-free guidance — it is distilled to not need it). This
script defaults to 1, the fastest documented setting, since it renders one image per scene and
speed matters more here than the marginal quality gain 2-4 steps buys; pass `--steps 4` for a
slower, slightly higher-quality pass.

New dependencies this script needs (`torch`, `diffusers`, and whatever they pull) are recorded
in `requirements-imagegen.txt`, a file deliberately separate from `requirements.txt` — those
are a multi-GB air-gap liability for every deployment, not just the ones that use this script.

Usage: python scripts/illustrate_panels.py <storyboard.json> --out <dir> [--steps N]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

CANVAS = (1280, 720)  # matches render/_video_svg.py and render/panels.py
DEFAULT_STEPS = 1
_MODEL_DIR = Path("models/imagegen")


def pair_scenes_with_panels(storyboard: dict[str, Any]) -> list[tuple[dict[str, Any], int]]:
    """Zip each scene (original order) with its non-extra panel's filename index.

    `data["panels"]` is in render order and includes spliced-in "extra" panels (infographic
    hero/chart) that never correspond to a scene; filtering to `is_extra == false` and zipping
    positionally against `data["scenes"]` recovers the correct pairing even when extras exist.
    """
    scenes = storyboard.get("scenes", [])
    scene_panels = [p for p in storyboard.get("panels", []) if not p.get("is_extra")]
    if len(scenes) != len(scene_panels):
        raise ValueError(
            f"storyboard scene/panel count mismatch: {len(scenes)} scenes vs "
            f"{len(scene_panels)} non-extra panels — regenerate storyboard.json"
        )
    return list(zip(scenes, (int(p["index"]) for p in scene_panels), strict=True))


def build_prompt(scene: dict[str, Any]) -> str:
    """A short single-sentence text-to-image prompt from a scene's visual recommendation."""
    visual = str(scene.get("visual_recommendation") or "").strip()
    description = str(scene.get("scene_description") or "").strip()
    if visual and description:
        return f"{visual}. {description}"
    return visual or description or "a plain informational illustration, no text"


def model_dir_ready(model_dir: Path) -> bool:
    """True when `model_dir` looks like a usable local diffusers snapshot."""
    return model_dir.is_dir() and (model_dir / "model_index.json").is_file()


def _load_pipeline(model_dir: Path) -> Any:
    """Load a local few-step diffusion pipeline. Heavy imports deferred to here on purpose."""
    import torch
    from diffusers import AutoPipelineForText2Image

    device = "cuda" if torch.cuda.is_available() else "cpu"
    pipe = AutoPipelineForText2Image.from_pretrained(
        str(model_dir), local_files_only=True, torch_dtype=torch.float32
    )
    return pipe.to(device)


def _fit_canvas(image: Any) -> Any:
    """Cover-fit crop `image` to exactly `CANVAS` (1280x720)."""
    from PIL import Image

    target_w, target_h = CANVAS
    scale = max(target_w / image.width, target_h / image.height)
    size = (round(image.width * scale), round(image.height * scale))
    resized = image.resize(size, Image.Resampling.LANCZOS)
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def illustrate(
    storyboard_path: Path, out_dir: Path, *, steps: int, model_dir: Path = _MODEL_DIR
) -> list[Path]:
    """Generate every scene's illustrated panel; raises when the local model is unusable."""
    if not model_dir_ready(model_dir):
        raise RuntimeError(
            f"no usable diffusion model found at {model_dir} (expected {model_dir}/"
            "model_index.json) — run the one-time fetch command documented in this script's "
            "own header, then re-run"
        )
    storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
    pairs = pair_scenes_with_panels(storyboard)
    pipe = _load_pipeline(model_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for scene, index in pairs:
        prompt = build_prompt(scene)
        result = pipe(prompt, num_inference_steps=steps, guidance_scale=0.0)
        image = _fit_canvas(result.images[0])
        target = out_dir / f"panel_{index:02d}.png"
        image.save(target)
        written.append(target)
    return written


def main(argv: list[str] | None = None) -> int:
    """Parse args, illustrate every scene panel, report, and exit non-zero on any failure."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("storyboard", type=Path, help="path to a rendered storyboard.json")
    parser.add_argument("--out", type=Path, required=True, help="directory to write panels into")
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS, help="diffusion steps")
    args = parser.parse_args(argv)
    if not args.storyboard.is_file():
        print(f"error: storyboard file not found: {args.storyboard}", file=sys.stderr)
        return 1
    try:
        written = illustrate(args.storyboard, args.out, steps=args.steps)
    except Exception as exc:  # noqa: BLE001 - report and exit; no partial output directory
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {len(written)} panel(s) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
