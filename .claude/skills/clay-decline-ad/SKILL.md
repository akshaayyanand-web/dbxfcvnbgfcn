---
name: clay-decline-ad
description: Build a 3D soft-clay "decline timeline" infomercial ad in the proven Down-to-Ground style — the format that dramatizes a person's multi-year physical/financial/emotional decline from ignoring a common, passively-compounding problem, then hard-cuts from clay animation to REAL product footage as the one passive fix. Brand-agnostic. Collects brand vars every run, writes the full 7-beat narrator script (long-form ~100-150s or 30s cutdown), then per-scene image keyframe + image-to-video prompts following the clay visual system (soft-clay render, aging protagonist, red-problem/green-fix color binary, 2D squiggle pain overlays, karaoke captions, year-marker cards, clay->real product cut). Optionally renders. Use when the user types /clay-decline-ad or asks to make a claymation / clay-style decline / "what happens over N years" timeline ad.
---

# /clay-decline-ad — soft-clay "passive decline timeline" ad builder

Produces a complete ad in the style reverse-engineered from the viral "Down to Ground"
inflammation infomercial (9/10): a 3D soft-clay character declines over N years from
ignoring a common, passively-compounding problem, then the ad cuts to the product as the
simple passive brake.

Always read reference/style-bible.txt first. It is the canonical formula.

Pipeline:
1. Collect inputs — brand vars + the problem (must be common, minor-early, passively compounding).
2. Write the script — the 7-beat Passive Decline Timeline narrator VO.
3. Build per-scene prompts — clay keyframe + image-to-video prompts following the visual system.
4. Render (optional) — hand off or render the scenes.

## Step 0 — Set up the run
Create a run dir: state/runs/[timestamp]/ (current datetime). Read reference/style-bible.txt first.

## Step 1 — Collect inputs (ask all at once)
This format only works when the problem is common, feels minor early, and compounds
PASSIVELY over years during an activity the product targets. If acute/one-time, redirect.
Ask for: brand name + spelling; brand pronunciation; product name; product category;
the decline problem (1 sentence); the passive activity it compounds during; the timeline +
unit; core mechanism in plain language; tactile analogy ("less like X, more like Y") REQUIRED;
the 3 dumb-simple usage steps; target avatar (demographic + specific frustration);
credibility stack (studies / numbers / "N+ people" / guarantee) — must be real numbers the
user actually has, never invented; offer / urgency; product reference image (path or URL);
format (long-form ~100-150s or 30s cutdown).
If the user already attached the product image or gave a product URL, don't ask again.

## Step 2 — Write the narrator script
Follow Section 3 of the style-bible exactly — 7 beats.
VO hard rules: single calm serious documentary narrator; no em dashes; no bold;
connected sentences, no two-word stutter fragments; hook owns the first 5 words;
mechanism in plain language + the tactile analogy verbatim; CTA uses the locked formula
"Click below to [ACTION] before [URGENCY] and finally [EMOTIONAL PAYOFF]" plus the
interactive "check what year you're at" hook; ~75% problem / 25% solution; read aloud.
Every claim, statistic, study reference, and mechanism description must be true and
traceable to something the user actually provided — never fabricate a credibility signal,
and never soften how rigorously you check a claim just because it will be spoken over
animation instead of a real person. If the user can't substantiate something, cut it or
say it more honestly instead of dressing it up as science. Save as [run_dir]/script.txt —
narrator VO only, timestamped by beat.
Self-audit against the failure modes before saving.

## Step 3 — Build per-scene prompts
Save as [run_dir]/scene_prompts.json. Default split mirrors the beats (one per beat,
split year markers if needed; 30s cutdown = 5 scenes).
Each scene object has: scene, beat, duration_sec, aspect_ratio, render_mode
("clay" or "real"), image_url, keyframe_prompt, video_prompt, captions, on_screen_text.
Rules: clay scaffold on every animated keyframe; continuity (same protagonist + home,
only the aging changes); color binary (red problem / green fix, never both pre-turn);
ghost beat; product scenes use the product image; name the camera move per beat,
no locked-off shots; captions optional (omit for a clean cut).

## Step 4 — Render (optional) — HARD WAIT, costs money
Ask before rendering. Either hand off the prompts, or render: clay keyframes ->
image-to-video each scene via the connected MCP video tools (Arcads/Seedance,
higgsfield, fal). 9:16, 720p, audio optional. Confirm cost first.

## Step 5 — Hand off
Print: run dir path, all deliverable file names, the narrator script in a code block,
and the reminder to stitch scenes, add the VO + ambient bed, and add captions if wanted.

## Important behaviors
- Brand-agnostic. Prompt for inputs fresh every run.
- .txt for the script deliverable.
- Read reference/style-bible.txt first.
- Refuse-and-redirect if the problem isn't passive/compounding.
- Self-audit against the failure modes before saving.
- Hard wait before any paid render.
- Truthfulness is non-negotiable: never invent statistics, studies, testimonials, or
  "N+ people" claims, and never treat the animated medium as license to say something
  that would be irresponsible or misleading if said plainly by a real person. If a claim
  can't be substantiated, cut it or soften it to something honest.
