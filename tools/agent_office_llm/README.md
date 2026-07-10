# Office Director — live LLM conversation layer

Turns the Virtual Agent Office's static briefing NPCs into per-character LLM agents you
can walk up to and talk to. The perception, proximity, llm-play brain dispatch,
Office Service handoff, and act-payload wiring are real and runnable. Voice in/out is
still the next major stub.

Full build spec: [`../../journal/agent_office/LLM_CONVERSATION_LAYER.md`](../../journal/agent_office/LLM_CONVERSATION_LAYER.md)
· vision: [`../../../llm-play/VISION.md`](../../../llm-play/VISION.md)

## Try it now (no game required)

```bash
python3 tools/agent_office_llm/office_director.py --dry-run
python3 tools/agent_office_llm/office_director.py --dry-run --utterance "what are you working on?"
python3 tools/agent_office_llm/office_director.py --dry-run --llm --backend ollama --utterance "what are you working on?"
```

Runs one perceive→engage→act cycle against a bundled fixture (player standing between the
Security and Director agents) and prints the act payloads the director would POST.
`--llm` loads the sibling `llm-play` backend (`auto`, `ollama`, or `mlx`); without it,
the director uses deterministic scripted fallback lines.

## Run live (after engine work)

```bash
python3 tools/agent_office_llm/office_director.py --url http://127.0.0.1:8780 --llm --backend auto
./scripts/start-agent-office-director.sh
./scripts/start-agent-office-director.sh --stop
```

Requires the two additive bridge changes in the spec §3: `/observe` emitting `agents[]`
and `/act` accepting `agents[].say`. Until then the director falls back to scanning
`actors[]` and simply won't see the office chrs.

From Perfect Dark Kit, open **Agent Office**, then use **Start Live Director**. The same
start/stop actions are also exposed in the Kit Hub's **Scenarios & Launch** section.

## Run as the Projex / PragChat host service

This is the ASAP integration path: Projex keeps PragChat and project management as the
primary host, while Perfect Dark is the 3D spatial tab over the same Office Service
state.

```bash
./scripts/start-agent-office-service-api.sh
curl http://127.0.0.1:8791/health
curl http://127.0.0.1:8791/pragchat/manifest
curl http://127.0.0.1:8791/pragchat/snapshot
./scripts/start-agent-office-service-api.sh --stop
```

Projex / PragChat should load `GET /pragchat/manifest` for the system prompt and
resource definitions, then poll or subscribe against `GET /pragchat/snapshot` for
channels, agent DMs, threads, approvals, tasks, events, and fleet status. The same
service also exposes the direct control-plane routes:

| Route | Purpose |
|-------|---------|
| `GET /agents`, `GET /agents/:id` | Inspect the 3D/PragChat agent roster |
| `GET /tasks`, `GET /tasks/:id` | Inspect assigned work |
| `POST /dispatch` | Create an agent task from PragChat or Projex project UI |
| `POST /tasks/:id/perform` | Run/stage connector actions for a task |
| `GET /approvals`, `GET /approvals/:id` | Render human-present approval cards |
| `POST /approvals/:id/approve`, `POST /approvals/:id/deny` | Resolve staged write actions |
| `POST /slack/ingest` | Ingest Slack-style messages into the Office event bus |
| `GET /events`, `POST /events` | Replay or append shared world/chat events |
| `GET /fleet` | Show blocked/ready agent status |

Keep this as one state core: PragChat, Projex project views, and the Perfect Dark office
must all read/write through this service rather than maintaining separate task,
approval, or audit stores.

## Layout

| Path | Role |
|------|------|
| `office_director.py` | Perception, proximity engine (hysteresis + view cone), brain dispatch, act payloads, dry-run |
| `office_service_api.py` | Local HTTP entrypoint for Projex/PragChat host integration |
| `characters/<slug>/brain.json` | Per-agent persona, chrnum binding, voice slug, knowledge (knows/withholds) |
| `service/` | **Office Service** — the control-plane core (VISION §6): tasks, event bus, connector gateway, dispatch/approvals |

## Office Service (`service/`)

The persistent control plane the 3D client drives (VISION_AND_PRODUCT.md §6). Pure stdlib,
in-memory, unit-tested by `tests/test_office_service.py` and
`tests/test_office_service_http_api.py`:

| Module | Role |
|--------|------|
| `models.py` | Agent, Task, Approval, Event, AuditEntry + Autonomy/status enums (§6.5) |
| `event_bus.py` | Append-only, replayable world event bus (§6.6) |
| `connectors.py` | Connector Gateway — per-agent/per-tool **autonomy** (`suggest`/`ask-approval`/`act`) + **audit**; Slack/PagerDuty/GitHub stubs mirroring MCP shapes (§5) |
| `office_service.py` | Dispatch, the human-present **approval** gate, Slack round-trip, fleet status (§3, §6) |
| `http_api.py` | Stdlib JSON API + PragChat manifest/snapshot projection for Projex |
| `account_pool/` | **Account pooling** — typed lease lifecycle for LLM/connector credentials ([`ACCOUNT_POOL_SPEC.md`](../../journal/agent_office/ACCOUNT_POOL_SPEC.md)) |

```python
from service import Agent, Autonomy, ConnectorGateway, OfficeService
from service.connectors import slack_stub
gw = ConnectorGateway(); gw.register(slack_stub())
svc = OfficeService(gw)
svc.add_agent(Agent(id="comms", role="Comms", chrnum=0x38, tools=["slack"],
                    autonomy={"slack": Autonomy.ASK_APPROVAL}))
t = svc.dispatch("comms", "reply to marketing")
svc.perform(t, [{"connector":"slack","action":"post_message","args":{"text":"Friday."}}])
# t is AWAITING_APPROVAL — nothing sent until a human approves:
svc.approve(svc.pending_approvals()[0].id, decided_by="moi")   # now it posts, audited
```

Swap the stub `.call` bodies in `connectors.py` for real MCP invocations to go live.

## Next (phased — see spec §6)

- **C1** engine: `/observe` `agents[]` pass in `port/src/llm_observe.c` — **written** (needs build)
- **C2** engine: `/act` `agents[].say` → `hudmsgCreate` in `port/src/llm_bridge.c` — **written** (needs build)
- **C3** brain: llm-play backend replies + director→Office Service utterance dispatch — **written** (`--llm`)
- **C4** host: Projex/PragChat Office Service API + manifest/snapshot — **written**
- **C5** voice: wire `listen_player` / `speak` to `voice_pipeline/` (ASR in, TTS out)
- **C6** memory + `face_player` + world events; real MCP connectors behind the gateway (Slack first)
