# Office Director — live LLM conversation layer (scaffold)

Turns the Virtual Agent Office's static briefing NPCs into per-character LLM agents you
can walk up to and talk to. **Scaffold stage** — the perception, proximity, brain-dispatch,
and act-payload wiring are real and runnable; the engine bridge extensions, LLM backend,
and voice are stubbed with clear TODOs.

Full build spec: [`../../journal/agent_office/LLM_CONVERSATION_LAYER.md`](../../journal/agent_office/LLM_CONVERSATION_LAYER.md)
· vision: [`../../../llm-play/VISION.md`](../../../llm-play/VISION.md)

## Try it now (no game required)

```bash
python3 tools/agent_office_llm/office_director.py --dry-run
```

Runs one perceive→engage→act cycle against a bundled fixture (player standing between the
Security and Director agents) and prints the act payloads the director would POST.

## Run live (after engine work)

```bash
python3 tools/agent_office_llm/office_director.py --url http://127.0.0.1:8780
```

Requires the two additive bridge changes in the spec §3: `/observe` emitting `agents[]`
and `/act` accepting `agents[].say`. Until then the director falls back to scanning
`actors[]` and simply won't see the office chrs.

## Layout

| Path | Role |
|------|------|
| `office_director.py` | Perception, proximity engine (hysteresis + view cone), brain dispatch, act payloads, dry-run |
| `characters/<slug>/brain.json` | Per-agent persona, chrnum binding, voice slug, knowledge (knows/withholds) |

## Next (phased — see spec §6)

- **C1** engine: `/observe` `agents[]` pass in `port/src/llm_observe.c`
- **C2** engine: `/act` `agents[].say` → `aiShowHudmsg` in `port/src/llm_bridge.c`
- **C3** brain: replace `AgentBrain.respond` stub with an llm-play `AdapterOrchestrator`
- **C4** voice: wire `listen_player` / `speak` to `voice_pipeline/` (ASR in, TTS out)
- **C5** memory + `face_player` + world events
