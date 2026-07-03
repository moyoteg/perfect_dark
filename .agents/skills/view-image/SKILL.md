# Skill: view-image

View, analyze, and describe images (screenshots, renders, textures) using image-to-text tools.

## Usage

When the user asks to view, check, or analyze an image:

1. Read the image file using the Read tool (supports PNG, JPEG, GIF, BMP, etc.)
2. If the file path is relative, resolve it relative to the workspace root.
3. If Read returns the image, describe what you see in detail (colors, shapes, UI elements, text, etc.)

## Supported formats

- PNG, JPEG, GIF, BMP, TIFF, WebP

## Notes

- If the model cannot read images, inform the user and suggest workarounds (e.g., check file metadata, use `sips`/`ffmpeg` to extract info).
- For games: describe UI layout, HUD elements, geometry/colors, any visible text, and overall composition.
