# replication-troy — canonical worked example

A full run through Phases 1–8 at 30 seconds (N=3 blocks), condensed to show
the *shape* of every phase's output. When any phase's output format is
unclear, match this example rather than inventing a new shape.

## Phase 1–2: Topic + Angle
**Topic:** The Trojan Horse.
**Angle:** Everyone believes Greek soldiers hid inside a giant wooden horse
and Troy wheeled it in as a gift — but archaeologists now think the "horse"
was Poseidon, god of earthquakes, and the real mechanism was a collapsing
wall.

## Phase 3: Script (81 words ≈ 30s)
> Greek soldiers built a giant wooden horse, hid inside, and Troy wheeled it
> in as a gift. The horse never rolled through any gate — because the gate
> wasn't standing anymore. Troy's dig site shows a fault line snapped through
> the foundation, towers cracked and collapsed inward, right when the war
> ended. Poseidon, blamed for earthquakes, was also the god of horses — so a
> quake got remembered as his gift. The Trojans didn't drag in a trap. They
> walked through the wound.

Beats: Myth (17w) / Twist (13w) / Mechanism A (21w) / Mechanism B (18w) /
Kicker (12w).

## Phase 4: Scene plan (N=3)

| Block | Beats covered | Shots |
|---|---|---|
| 1 (0-10s) | Myth → Twist | 7 |
| 2 (10-20s) | Mechanism A | 6 |
| 3 (20-30s) | Mechanism B → Kicker | 7 |

**Block 1 shot list:**
```
[00:00-01.3] WS, low-angle — the wooden horse wheeled toward Troy's gate at dusk — no annotation — assets: horse, gate-environment(intact)
[01.3-02.5] MCU, eye-level — a Trojan soldier's face, uncertain — no annotation — assets: trojan-soldier
[02.5-03.6] MACRO, high-angle — horse's carved wooden eye, torchlight reflecting — no annotation — assets: horse
[03.6-05.0] MS, dutch tilt — soldiers straining on ropes pulling the horse — no annotation — assets: trojan-soldier, horse
[05.0-06.4] WS, high-angle — the horse passing under the gate arch — GREEN outline on the gate's foundation stones — assets: gate-environment(intact)
[06.4-08.0] CU, low-angle — a mason's hand tracing a hairline crack in the stone — GREEN outline on the crack — assets: gate-environment(intact)
[08.0-10.0] MS, eye-level — soldiers celebrating, unaware, gate looming behind — no annotation — assets: trojan-soldier, gate-environment(intact)
```
(this is the "gag" beat's setup — the celebration reads as relief, not
suspicion, right before block 2 shows why that was wrong)

**Asset roster:**
| Asset | Type | Appears in | Notes |
|---|---|---|---|
| trojan-soldier | person | 1, 3 | one recurring hero soldier |
| horse | object | 1 | carved oak, bronze fittings |
| gate-environment — intact | environment | 1 | dusk, torches lit |
| gate-environment — cracked | environment | 2 | damage state of the same plate |
| gate-environment — breached | environment | 3 | damage state of the same plate |

## Phase 5: Character sheets

**Style key prompt:** the wooden horse silhouetted against Troy's torchlit
gate at dusk, cobalt sky deepening above, warm torch glow along the wall —
this single still anchors the palette for every asset sheet below.

**Sample person sheet (trojan-soldier):**
```
{STYLE FORMULA} — CHARACTER SHEET, Trojan gate-watchman, full body, front 3/4
view, neutral flat grey backdrop, arms slightly away from body, bronze
scale-mail cuirass over a linen tunic, leather greaves, a short growth of
beard and a horsehair-crested helmet tucked under one arm as his silhouette
cue. {NEGATIVE}
```

**Sample environment sheet (gate-environment, intact state):**
```
{STYLE FORMULA} — ENVIRONMENT SHEET, EMPTY LOCATION PLATE, take only the
render style and palette from the reference image, NOT its subject, a
towering dressed-stone city gate at dusk with unlit torch brackets, intact
foundation, dressed set, no people. ABSOLUTELY NO trojan-soldier, NO horse,
NO people, NO animals. {NEGATIVE}
```

## Phase 6: Sample block prompt (Block 1, full)
```
{STYLE FORMULA}

TIMED CUTS (10s):
[00:00-00:01.3] WS, low-angle — the wooden horse is wheeled toward the city
gate at dusk by straining soldiers — no annotation
[00:01.3-00:02.5] MCU, eye-level — a Trojan gate-watchman's face, uncertain,
watching the horse approach — no annotation
[00:02.5-00:03.6] MACRO, high-angle — the horse's carved wooden eye catching
torchlight — no annotation
[00:03.6-00:05.0] MS, dutch tilt — soldiers straining on ropes, the horse
lurching forward — no annotation
[00:05.0-00:06.4] WS, high-angle — the horse passes under the gate arch —
GREEN glowing outline hugging the gate's foundation stones
[00:06.4-00:08.0] CU, low-angle — a mason's hand traces a hairline crack in
the foundation stone — GREEN glowing outline tracing the crack
[00:08.0-00:10.0] MS, eye-level — soldiers celebrate, unaware, the gate
looming behind them — no annotation

Characters only emote and gesture, they do NOT talk. No lip-sync, no mouth
movement forming words. Audio: mute or diegetic ambience only, no dialogue.

{NEGATIVE}
```

## Phase 7: Narration call
```
[confident documentary narrator, deliberate storytelling pace with natural
beats between sentences, starts speaking immediately] [00:00-00:29]
Greek soldiers built a giant wooden horse, hid inside, and Troy wheeled it in
as a gift. The horse never rolled through any gate — because the gate wasn't
standing anymore. Troy's dig site shows a fault line snapped through the
foundation, towers cracked and collapsed inward, right when the war ended.
Poseidon, blamed for earthquakes, was also the god of horses — so a quake got
remembered as his gift. The Trojans didn't drag in a trap. They walked
through the wound.
```
Target duration: 28.5s (N×10 − 1.5s).

## Phase 8: Sample edit_map.json
```json
[
  {"type": "punch", "time": 6.2, "duration": 0.4},
  {"type": "shake", "time": 9.6, "duration": 0.3},
  {"type": "punch", "time": 14.0, "duration": 0.4},
  {"type": "shake", "time": 19.6, "duration": 0.3},
  {"type": "shake", "time": 22.4, "duration": 0.3},
  {"type": "punch", "time": 27.5, "duration": 0.4}
]
```
Punches land on the two GREEN-outline reveals and the kicker; shakes land on
both block boundaries (9.6s, 19.6s) plus the breach impact in block 3
(22.4s).
