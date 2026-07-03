# Game LLM (moved)

Canonical **LLM Play** project: [`../../llm-play`](../../llm-play) (sibling under `Games/`).

This folder keeps a thin shim so existing commands still work:

```bash
python3 tools/game_llm/run_adapter.py --game perfect_dark
```

Prefer working from the llm-play project:

```bash
cd ../llm-play
./scripts/rebuild-relaunch-llm-play.sh
```

Game bridge code stays in this repo (`port/src/llm_bridge.c`, `port/src/llm_player.c`). Runtime logs: `journal/game_llm/perfect_dark/`.
