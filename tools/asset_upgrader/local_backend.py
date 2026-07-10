"""Free local texture enhancement — no API key, no per-image billing."""

from __future__ import annotations

import time
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter


class LocalTextureUpgrader:
    """Enhance N64-style textures on-device (pixel-art aware upscale + sharpen)."""

    def __init__(self, *, scale: int = 4, dry_run: bool = False) -> None:
        self.scale = max(2, min(scale, 8))
        self.dry_run = dry_run

    @staticmethod
    def _is_pixel_art(image: Image.Image, sample: int = 4096) -> bool:
        rgba = image.convert("RGBA")
        pixels = list(rgba.getdata())
        step = max(1, len(pixels) // sample)
        sample_set = {pixels[i] for i in range(0, len(pixels), step)}
        return len(sample_set) <= 64

    def _enhance(self, image: Image.Image) -> Image.Image:
        rgba = image.convert("RGBA")
        w, h = rgba.size
        scale = self.scale
        pixel_art = self._is_pixel_art(rgba)

        if pixel_art:
            big = rgba.resize((w * scale, h * scale), Image.Resampling.NEAREST)
            big = big.filter(ImageFilter.UnsharpMask(radius=1.2, percent=180, threshold=1))
            big = ImageEnhance.Contrast(big).enhance(1.08)
            out = big
        else:
            big = rgba.resize((w * scale, h * scale), Image.Resampling.LANCZOS)
            big = big.filter(ImageFilter.UnsharpMask(radius=1.5, percent=140, threshold=3))
            big = ImageEnhance.Contrast(big).enhance(1.05)
            big = ImageEnhance.Sharpness(big).enhance(1.15)
            out = big

        return out

    def upgrade_png(self, src: Path, dst: Path, *, width: int, height: int) -> dict:
        started = time.time()
        image = Image.open(src).convert("RGBA")
        if image.size != (width, height):
            image = image.resize((width, height), Image.Resampling.NEAREST)

        if self.dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            image.save(dst)
            return {"status": "dry_run", "backend": "local", "output": str(dst)}

        out = self._enhance(image)
        dst.parent.mkdir(parents=True, exist_ok=True)
        out.save(dst)
        return {
            "status": "ok",
            "backend": "local",
            "mode": "pixel_art" if self._is_pixel_art(image) else "smooth",
            "seconds": round(time.time() - started, 3),
            "output": str(dst),
        }
