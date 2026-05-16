# End4D Backend Engine Reform Target

> Version: 16.05.2026.v2  
> Purpose: Make End4D feel like a live, fast, high-density social-field simulation while preserving its own identity.

---

## 1. Why This Exists

The current engine has many good parts, but the user experience still feels too much like this:

```text
compute a whole t step
→ finish hidden interaction
→ display the result
```

The target experience is different:

```text
enter t
→ agents immediately start lightweight consultation beats
→ visual field tails those beats in real time
→ t boundary performs deeper 3-tier cognition
→ review explains why the field changed
```

The goal is not "more animations". The goal is that the backend itself should produce a fast action stream that the frontend can honestly visualize.

---

## 2. MiroFish Lessons, Reinterpreted For End4D

MiroFish's public README describes a pipeline that extracts seed information from real-world material, constructs a high-fidelity parallel digital world, and lets thousands of agents with independent personalities, memory, and behavioral logic interact and evolve. It also describes a workflow:

```text
Graph Building
→ Environment Setup
→ Simulation
→ Report Generation
→ Deep Interaction
```

Source references:

- <https://github.com/666ghj/MiroFish>
- <https://github.com/666ghj/MiroFish/blob/main/README.md>
- <https://github.com/666ghj/mirofish/blob/main/backend/app/api/simulation.py>

End4D should absorb the structure, not the domain or code.

| MiroFish structural lesson | End4D translation |
|------|------|
| Seed extraction before simulation | `ScenarioCompiler` normalizes prompt into domain, actors, zones, conflict axes, observables |
| Persona/config generation before run | `ActorFactory` creates actor sheets with name, role, occupation, zone, goal, fear, speech style |
| OASIS-style swarm loop | `ConsultationKernel` runs cheap active-agent rounds inside t |
| Action/history logs tail the simulation | `ActionLedger` records End4D social-field events, not social-media actions |
| Report/agent interview after simulation | Review/Chat explain snapshots, scene events, persona state, and causal metadata |

Forbidden:

- Do not copy MiroFish code.
- Do not imitate social-media platforms as the core domain.
- Do not replace End4D's `x/y/z/t`, social elevation, pressure, worldview, and review causality model.

---

## 3. End4D Identity Lock

End4D is a 4D social-field engine:

```text
agent/persona
→ local relationship and pressure field
→ zone/social elevation
→ t-internal consultation beats
→ t-boundary deep cognition
→ reviewable causal explanation
```

The unit of simulation is not a post, like, comment, or platform event.

The unit of simulation is:

```text
FIELD_CONTACT
FIELD_ALIGN
FIELD_CONTEST
FIELD_NEGOTIATE
FIELD_PRESSURE_SHIFT
FIELD_DRIFT
DEEP_COMMIT
```

Every backend change must answer:

> Does this make the `x/y/z/t` social field faster, more alive, more persona-grounded, or more explainable?

If not, it is not core work.

---

## 4. Target Backend Architecture

```text
Raw Prompt / Documents
  ↓
Scenario Compiler
  - normalize short prompts
  - infer domain / country / actors / zones / conflict axes
  - identify observables and shock candidates
  ↓
Actor Factory
  - name
  - social role
  - occupation
  - zone
  - goal / fear
  - speech style
  - relationship bias
  ↓
World Factory
  - initial field placement
  - zone/bloc topology
  - initial pressure and z-field
  - scenario-sensitive distribution
  ↓
Live Consultation Runtime
  - active-agent subset
  - local neighbor matching
  - compact rule-based consultation beats
  - immediate WebSocket flush
  - no LLM per micro beat
  ↓
Deep Commit Runtime
  - t-boundary Thought/Action/Worldview
  - LLM packet/agent modes
  - group deliberation
  - belief trajectory
  ↓
Review / Chat / Dashboard
  - causal summary
  - scene/event grounding
  - agent interview
  - policy comparison
```

---

## 5. Non-Negotiable Product Feel

### 5.1 t Should Feel Like A Period, Not A Snapshot

The user selects discrete `t`, but inside a selected/running `t`, agents should visibly interact like a short live chapter.

```text
t=4
  beat 1: local contacts
  beat 2: negotiation / disagreement
  beat 3: pressure propagation
  beat 4: movement / drift
  beat 5: group signal
  beat 6: deep commit
```

### 5.2 Fast Means Backend Events, Not Fake UI Motion

The frontend should not fake life by animating stale snapshots.

The backend must stream:

- `scene`
- `action_event`
- `observer_cells`
- `progress`
- `phase`
- `heartbeat`
- `engine_revision`

### 5.3 LLM Is Strategic, Not Per-Particle

Inside t:

- rules, pressure, relationship, spatial proximity, and active subset selection should be fast.
- LLM should not block every local interaction.

At t boundary:

- LLM can summarize, interpret, choose strategies, and commit deeper cognition.

---

## 6. Current Gap Diagnosis

| Area | Problem | Impact |
|------|------|------|
| Step runtime | `step_loop_node` still orchestrates too many phases directly | Hard to reason about performance and streaming cadence |
| Scene generation | event selection and narrative rendering are mixed | Hard to tune speed and story quality independently |
| Memory writes | deep memory/belief writes can still dominate perceived runtime | t feels stuck before movement appears |
| WebSocket cadence | scene flush exists, but backend still emits too few meaningful beats under some paths | User sees sudden t jumps |
| Persona grounding | actor sheet exists, but thought/action/dialogue still need stronger person-like relation memory | Stream feels generic |
| World factory | placement is better, but initial topology is not yet a first-class module | worlds can still feel similarly arranged |
| Runtime observability | version string exists, but per-phase timing is not visible | hard to know if bottleneck is consultation, LLM, review, or serialization |

---

## 7. Reform Milestones

### Cleanup Decision — Standalone Swarm Runtime Removed

The old standalone `/swarm/run` backend and `app/swarm/*` engine were removed from the active codebase.

Reason:

- It was not the path users were actually experiencing; the pain is in the precision runtime.
- It duplicated the product direction while failing to deliver MiroFish-like feel.
- It added tests, APIs, and mental overhead without improving the live social field.

Swarm remains a product direction, but it must now be rebuilt inside the main social-field runtime:

```text
precision t step
→ fast intra-t lightweight consultation
→ t-boundary deep cognition
→ reviewable causal ledger
```

No separate scarecrow engine until the main path feels alive.

### Milestone A — Runtime Split

Goal: make the backend loop obvious and fast.

Deliverables:

- `world_factory.py`
- `consultation_kernel.py`
- `stream_episode_runtime.py` — first split implemented; one MiroFish-style stream episode now owns the fast t-internal consultation rounds.
- `deep_commit_runtime.py` — first split implemented; t-boundary action/dialogue/group deliberation now lives outside graph orchestration.
- `scene_selector.py` — first split implemented; scene selection is now isolated from narration.
- `scene_narrator.py` — first split implemented; labels, reasons, and pressure summaries are now isolated from selection.
- phase timing metadata in stream events — first implementation complete for `step` and `heartbeat` payloads.

Acceptance:

- `step_loop_node` becomes orchestration only.
- t-internal beats flush before deep commit.
- scene selection can be benchmarked without LLM.

### Milestone B — Live Consultation Feel

Goal: make t-internal activity feel fast and visible.

Deliverables:

- more frequent lightweight consultation beats
- active subset rotation guarantees
- immediate compact `FIELD_*` action records
- interaction sentiment and intensity from relationship state
- no persistent stale relationship trails unless replaying snapshot

Acceptance:

- running stream shows multiple events before the next full step snapshot.
- large worlds do not require full cell scanning for every beat.
- UI can draw edges from real backend events.

Status:

- `consultation-kernel-v5-swarm-session-density` raises the default precision intra-t beat density while preserving explicit user overrides.
- `consultation-kernel-v6-stable-stream-density` raises the live scene cap and per-beat micro consultation floor so stream playback has a steadier event supply without scanning the whole world.
- `consultation-kernel-v7-topic-expanding-stream` makes one topic gather a growing active cast across the stream episode and paces live scene emission so the UI can show consultation history before the next t snapshot arrives.
- `consultation-kernel-v8-independent-stream-session` treats each t as one independent stream session with a minimum visible duration, denser consultation beats, a larger growing active cast, and delayed t-boundary snapshot emission.
- `consultation-kernel-v9-fast-visible-stream` corrects the over-blocking v8 defaults: stream bootstrap and agent-matching events are emitted immediately, scene delay is near-zero, persistence is batched less aggressively, and the default active cast is tuned for responsiveness before density.
- Swarm Mode now bypasses the Precision `step_loop` and uses `miro_swarm_runtime.py`: a clean-room MiroFish-style session runner that emits many relationship events immediately, commits one End4D t snapshot at session end, and keeps End4D pressure/group/review metadata.
- Runtime config can now patch `initial_cell_count` before stream execution, and local persistence uses unique temp files so overlapping stream writes do not collide on the same `*.json.tmp` path.
- `stream_episode_runtime.py` now owns the full MiroFish-style t-internal stream: many lightweight consultation rounds run first, then the graph proceeds to thought/worldview and t-boundary commit.
- Each lightweight consultation beat now emits dense `micro_consultation` scene events immediately, before review-grade top-K scene selection.
- Each MiroFish-style stream activates a much larger rotating agent subset and fans out up to four visible target contacts per source, so one turn reads like many agents consulting in parallel instead of one or two highlighted edges.
- Each event in the same t now shares a `stream_episode_id`: one complete MiroFish-like stream composes one t, and the next t begins only after that stream completes.
- Live scene dedupe and final snapshot merging now allow the same relationship to reappear across distinct beat times, so a t interval can feel like a moving chapter instead of one static edge.
- Lightweight consultation payloads include person-like `micro_utterance`, target label, and consultation intensity for direct field visualization.
- Live observer payloads are built from the active beat cast instead of the full world, reducing per-scene overhead for larger worlds.

### Milestone C — Persona Grounding

Goal: agents should sound and behave like named people with roles, not role labels.

Deliverables:

- actor relationship memory summary
- dialogue/thought prompt grounding with last peer contact
- Korean natural action text by default
- separate identity fields: name, occupation, role, zone, motive

Acceptance:

- thoughts mention concrete interactions like "김아무개에게 이런 말을 듣고..."
- action summaries include behavior, reason, target.
- no synthetic UUID-like name appears as display name unless data truly lacks identity.

### Milestone D — Timing And Performance Visibility

Goal: stop guessing.

Deliverables:

- per-phase timing: policy, growth, stream_episode, scene_select, deep_commit, serialize
- stream payload byte estimates
- active agent count per beat
- LLM task timing and fallback reason

Acceptance:

- runtime panel can explain why a run feels slow.
- backend tests include a small perf budget for scene selection and consultation.

### Milestone E — Review/Chat Uses The Same Ledger

Goal: simulation, dashboard, chat, and review should explain the same causal source.

Deliverables:

- action ledger as shared grounding source
- scene event links to action record
- chat answer cites snapshot/persona/event metadata
- review diff cites pressure and relationship action records

Acceptance:

- asking "why did t=4 change?" returns cited scene/action evidence.

---

## 8. Immediate Implementation Order

1. Split `scene_events.py` into:
   - `scene_selector.py`
   - `scene_narrator.py`
   - status: first implementation complete; legacy `scene_events.py` remains as the public facade.
2. Add `runtime_timing.py` and phase timing to stream messages.
   - status: first implementation complete; next pass should surface these timings in RuntimeDock.
3. Extract deep commit from `nodes.py`.
   - status: first implementation complete; next pass should split thought/worldview commit and review payload generation.
4. Strengthen actor/persona identity propagation into thought/action/dialogue.
5. Add benchmark for:
   - 100 agents
   - 1k agents
   - scene selection latency
   - stream payload size

This is the path to an actual MiroFish-level experience, not another cosmetic patch.
