"""OpenAI image generation / edit backend for texture upgrades."""

from __future__ import annotations

import base64
import io
import os
import time
from pathlib import Path

from PIL import Image

from tools.asset_upgrader.auth import load_env_file

DEFAULT_PROMPT = (
    "Upscale and enhance this retro N64 game texture. Preserve the exact composition, "
    "silhouette, palette feel, and transparency. Add crisp detail and cleaner edges "
    "without changing the subject or adding new objects. Output must remain a game texture, "
    "not a photograph."
)


class OpenAIImageUpgrader:
    """Call ChatGPT/OpenAI image models to upgrade PNG textures."""

    def __init__(
        self,
        *,
        model: str = "gpt-image-1",
        prompt: str = DEFAULT_PROMPT,
        upscale_to: int = 1024,
        api_key: str | None = None,
        dry_run: bool = False,
    ) -> None:
        self.model = model
        self.prompt = prompt
        self.upscale_to = upscale_to
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.dry_run = dry_run
        self._client = None
        # Allow workdir .env when constructed from CLI/Electron without exported env.
        load_env_file(Path.cwd() / "work" / "asset_upgrader" / ".env")
        if not self.api_key:
            self.api_key = os.environ.get("OPENAI_API_KEY")

    @property
    def client(self):
        if self._client is None:
            if not self.api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY is not set. Export it or pass --api-key before upgrading."
                )
            from openai import OpenAI

            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def _api_canvas(self, width: int, height: int) -> tuple[int, int, str]:
        """Pick a gpt-image-1 supported size closest to the source aspect ratio."""
        if width > height * 1.15:
            return 1536, 1024, "1536x1024"
        if height > width * 1.15:
            return 1024, 1536, "1024x1536"
        return 1024, 1024, "1024x1024"

    def _prepare_input(self, src: Path, width: int, height: int) -> tuple[bytes, str]:
        image = Image.open(src).convert("RGBA")
        canvas_w, canvas_h, size = self._api_canvas(width, height)
        scale = min(canvas_w / max(width, 1), canvas_h / max(height, 1))
        target_w = max(1, round(width * scale))
        target_h = max(1, round(height * scale))
        resized = image.resize((target_w, target_h), Image.Resampling.NEAREST)
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        canvas.paste(resized, ((canvas_w - target_w) // 2, (canvas_h - target_h) // 2))
        buf = io.BytesIO()
        canvas.save(buf, format="PNG")
        return buf.getvalue(), size

    def upgrade_png(self, src: Path, dst: Path, *, width: int, height: int) -> dict:
        if self.dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            Image.open(src).convert("RGBA").save(dst)
            return {"status": "dry_run", "model": self.model, "output": str(dst)}

        png_bytes, size = self._prepare_input(src, width, height)
        started = time.time()

        # Prefer edit when we have a reference image; fall back to generation.
        try:
            response = self.client.images.edit(
                model=self.model,
                image=("source.png", png_bytes, "image/png"),
                prompt=self.prompt,
                size=size,
            )
            mode = "edit"
        except Exception:
            response = self.client.images.generate(
                model=self.model,
                prompt=f"{self.prompt}\nReference dimensions: {width}x{height}.",
                size=size,
            )
            mode = "generate"

        item = response.data[0]
        if item.b64_json:
            out_bytes = base64.b64decode(item.b64_json)
        elif item.url:
            import urllib.request

            out_bytes = urllib.request.urlopen(item.url).read()
        else:
            raise RuntimeError("OpenAI response did not include image data")

        out_img = Image.open(io.BytesIO(out_bytes)).convert("RGBA")
        dst.parent.mkdir(parents=True, exist_ok=True)
        out_img.save(dst)
        return {
            "status": "ok",
            "mode": mode,
            "model": self.model,
            "seconds": round(time.time() - started, 2),
            "output": str(dst),
        }
