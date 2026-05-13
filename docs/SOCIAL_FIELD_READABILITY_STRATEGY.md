# Social Field Readability Strategy

## Goal

Social Field should feel like a **legible analysis surface**, not a noisy demo reel.

The map now has a Pixi-rendered live field with DOM overlays. To keep it readable as effects grow,
we need explicit visual hierarchy rules.

## Core Principles

1. Field first, chrome second.
   - The user should read pressure, shock, and agent movement before they read UI decoration.
   - Overlays should explain the field, not compete with it.

2. One dominant signal per moment.
   - Normal state: pressure field is primary.
   - Hover/select: focused agent is primary.
   - Event/shock: shock becomes primary briefly, then recedes.

3. Light background, controlled contrast.
   - Use a bright analytical canvas.
   - Keep text and chips dark enough to read quickly.
   - Avoid dark glass and neon unless they serve a specific state change.

4. Defaults should be quiet.
   - `heat` and `clusters` can stay on by default.
   - `shock` and `drift` should default off in precision mode unless the user turns them on.
   - Every optional layer must justify its visual cost.

## Visual Hierarchy

### Level 1: Primary motion

- Pixi pressure field
- Cluster mass
- Agent movement

These three define whether the map feels alive.

Rules:
- Pressure should occupy area, not just sit under dots.
- Cluster mass should be softer than agents but broader than pressure cores.
- Agent hover/select should spike clearly above the field.

### Level 2: Context overlays

- Zone chips
- Anchor pins
- Hover chip

Rules:
- Keep overlays light, thin, and sparse.
- Use white or near-white surfaces with dark text in light mode.
- Avoid large opaque blocks that hide the field.

### Level 3: Secondary diagnostics

- Detail cards
- Legends
- Meta chips

Rules:
- These should never visually overpower the map.
- Use muted borders, subtle shadows, and low color saturation.

## Interaction Strategy

### Hover

- Immediate local effect.
- Scale + glow on the agent.
- No full-screen distraction.

### Selection

- Stronger than hover.
- Ring, pulse, and panel sync.
- Selection should remain readable at multiple zoom levels.

### Shock

- Brief dominant event.
- Ripple + flash + afterglow.
- Must decay quickly so the map returns to readable baseline.

### Camera

- Pan and zoom should feel like navigating a space, not moving HTML cards.
- DOM overlays must follow the same transform as the Pixi world.

## Noise Budget

Every layer consumes part of a fixed readability budget.

### Allowed at the same time

- Pressure
- Cluster
- Agents
- Light zone chips
- Sparse anchors

### Use carefully

- Drift arrows
- Strong shock flash
- Dense annotation labels

### Avoid by default

- Multiple competing outlines
- Large dark glass overlays
- Persistent contour fields over the live renderer

## Immediate Next Steps

1. Finish light-mode cleanup for all Social Field surfaces.
2. Keep precision defaults quiet:
   - `heat`: on
   - `clusters`: on
   - `anchors`: on
   - `shock`: off
   - `drift`: off
3. Reduce overlay footprint further if zone chips still dominate the field.
4. Add a camera reset affordance once pan/zoom is fully stable.
5. Revisit shock intensity after light-mode review, because strong flashes can become harsher on bright canvases.

## Success Criteria

The map is readable when:

- the user can identify the main pressure region within 1-2 seconds,
- hover/select states are obvious without obscuring neighbors,
- zone/anchor overlays remain readable but feel secondary,
- pan/zoom preserves coherence,
- the scene still looks like a live field rather than layered UI cards.
