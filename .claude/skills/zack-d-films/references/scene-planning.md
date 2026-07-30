# scene-planning — from script to shot list

This turns a locked script into the two things the rest of the pipeline
consumes: a timed shot list per 10s block (§2), and the exact prompt shape
each block gets submitted as (§3), plus the edit grammar the final cut applies
on top (§4).

## §1 — Block breakdown
`N = ceil(duration / 10)`. Distribute the 5 script beats across the N blocks
by where they fall in time, not by forcing one beat per block — a 3-block
(30s) short typically lands close to:
- Block 1: Myth → Twist
- Block 2: Mechanism A → start of Mechanism B
- Block 3: rest of Mechanism B → Kicker

Longer scripts get more blocks per beat; a single beat can span more than one
block if its mechanism needs more visual room. Use the narration's actual
word timing (once you have it in Phase 7) to true up block boundaries —
before that, split evenly by word count as a working estimate.

## §2 — Shot list rules
Zack pacing is **6–9 hard cuts per 10s block** (~1.0–1.6s per shot). For every
shot write one line:

`[t0–t1] SIZE/ANGLE — subject + action — annotation (if any) — assets used`

**Size vocabulary:** MACRO/ECU (extreme close, eye/texture/detail), CU
(close-up, face or hands), MCU (medium close, chest-up), MS (medium, waist-
up), WS (wide, full body + setting), EWS (extreme wide, establishing).
**Angle vocabulary:** eye-level, low-angle (hero/threat), high-angle
(vulnerable/overview), dutch tilt (disorientation), over-shoulder.
**Camera energy:** push-in, whip-pan, crash-zoom, slow orbit — name it per
shot, don't leave it static by default.

Rules for every block:
- Vary size **and** angle on every single cut — never repeat the same
  size+angle back to back.
- At least one MACRO eye/detail shot somewhere in the whole video.
- One "gag" beat somewhere in the whole video — a vanish-poof, a deadpan
  reveal, a comedic beat that breaks the tension for one shot.
- Annotations follow the green/red grammar in `style-3d.md` — green for
  reveal/mechanism, red for danger/physics, never both in one shot.
- Every shot names which character-sheet assets appear in it — this is what
  the asset roster is for.

**Asset roster:** list every character, object, and environment that appears
in **two or more** shots (one-off background dressing doesn't need a sheet).
Include damage/wear states as separate roster rows when the story needs them
(e.g. `wall — intact`, `wall — cracked`, `wall — breached`) since each state
needs its own generated sheet in Phase 5.

Post the block table + roster in chat as one compact table each — this is
the production plan, and per Phase 4 it doesn't need a separate approval
gate (the script lock already was one).

## §3 — Cut-list → video prompt template
Phase 6 submits one `gemini_omni` call per block. Rewrite that block's shot
list into this shape (this is the literal prompt body):

```
{STYLE FORMULA from style-3d.md, byte-identical}

TIMED CUTS (10s):
[00:00-00:01.2] MACRO, low-angle — {subject} — {action} — no annotation
[00:01.2-00:02.6] WS, eye-level — {subject} — {action} — GREEN outline on {part}
[00:02.6-00:04.0] ...
... (continue through the block's full shot list, one line per shot,
     timecodes must sum to exactly 10s)

Characters only emote and gesture, they do NOT talk. No lip-sync, no mouth
movement forming words. Audio: mute or diegetic ambience only, no dialogue.

{NEGATIVE line from style-3d.md}
```

Keep every timecode contiguous (no gaps, no overlaps) and summing to exactly
10 seconds. Camera energy and annotation instructions from §2 go inline on
their shot's line, not bundled at the end — the model treats this as a
shot-by-shot edit decision list, not a mood board.

## §4 — Edit grammar (applied in Phase 8, after all blocks exist)
Two effects, applied on top of the concatenated render, timed against the
narration's beat map (Phase 7's word-level timestamps):

- **Punch** (zoom-in): scale 1.0 → ~1.08 over ~0.4s, on 3–6 of the biggest
  beat-map moments in the whole video — reveals, the moment an annotation
  appears, the kicker line. Don't punch on every cut; it should read as
  emphasis, not a tic.
- **Shake** (impact jitter): a ±1% crop-position jitter over ~0.3s, on every
  block boundary (masks the join) and every physical impact beat (the red
  annotation moments — cracks, bursts, trajectories landing).

Both are driven by `edit_map.json` (a flat list of `{type, time, duration}`
events) and applied by `scripts/zack_edit.py` — see that script and Phase 8
for the exact invocation.
