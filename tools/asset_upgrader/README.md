# Asset Upgrader

Mass-upgrade Perfect Dark mod textures for the PC port. **Default: free local enhancement**
(no API key, no per-image billing). Optional paid OpenAI backend available.

The PC port loads replacement textures from `MODDIR/textures/NNNN.bin`. This tool
decodes `.bin` → PNG, enhances them, re-encodes, and deploys to a mod folder.

## One command (free, recommended)

```bash
./scripts/run-asset-upgrader.sh mods
```

Uses the **local backend**: pixel-art-aware upscale + sharpen on your Mac. No ChatGPT
API, no extra cost.

## Backends

| Backend | Cost | Quality | Notes |
|---------|------|---------|-------|
| `local` (default) | Free | Good sharpen/upscale | Automated batch |
| `openai` | API billing | Best AI | Needs `OPENAI_API_KEY` |

ChatGPT Plus subscription **does not** power batch scripts — only the optional
`--backend openai` path uses platform API billing.

```bash
# Free (default)
python3 tools/asset_upgrader.py run --path mods --backend local

# Paid AI (optional)
export OPENAI_API_KEY=sk-...
python3 tools/asset_upgrader.py run --path mods --backend openai
```

## Setup

```bash
python3 -m venv .venv-asset-upgrader
source .venv-asset-upgrader/bin/activate
pip install -r tools/requirements-asset-upgrader.txt
```

## Electron supervisor

```bash
./scripts/build-asset-upgrader-electron.sh --run
```

## Play upgraded textures

```bash
./build/pd.arm64 --test-map --moddir mods/mod_upgraded
```

## Supported formats

- Zlib paletted (`CI4`/`CI8`) including **0x1172 and 0x1173** compression
- Non-zlib (Huffman, RLE, lookup, blur) → re-encoded as zlib CI on deploy

Encoded output must stay under **4096 bytes** (PC mod loader limit).
