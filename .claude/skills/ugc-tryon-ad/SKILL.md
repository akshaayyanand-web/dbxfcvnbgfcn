---
name: ugc-tryon-ad
description: Build a raw, handheld UGC-style try-on / product-demo ad — the format where a single believable "creator" unboxes, tries on, or demos a product on camera and casually recommends it, engineered to not look like an ad. Brand-agnostic. Collects brand vars every run, writes the full 6-beat "Honest Try" script (skeptical hook, unboxing, try-on, reaction, feature callout, soft CTA), then per-scene handheld try-on / demo prompts following the raw UGC visual system (no color grade, no cinematic lighting, natural light, imperfect framing). Optionally renders via Arcads fashion_tryon / product_showcase tools. Use when the user types /ugc-tryon-ad or asks for a UGC ad, try-on ad, testimonial-style ad, or product demo ad.
---

# /ugc-tryon-ad — raw UGC "honest try" ad builder

Produces a complete ad in the raw, handheld UGC try-on/demo style: one believable creator,
one setting, natural light, unscripted energy, ending in a casual recommendation.

Always read reference/style-bible.txt first. It is the canonical formula.

Pipeline:
1. Collect inputs — brand vars + the angle (who's talking, why they were skeptical, what changed their mind) + whether the user has their own script.
2. Write the script — the 6-beat "Honest Try" narrator/creator VO (skip if the user supplied their own).
3. Build per-scene prompts — handheld UGC keyframe + video prompts following the visual system.
4. Render (optional) — hand off or render the scenes.

## Step 0 — Set up the run
Create a run dir: state/runs/[timestamp]/ (current datetime). Read reference/style-bible.txt first.

## Step 1 — Collect inputs (ask all at once)
First ask: "Do you already have a script, or should I write one?" If they have one, ask
them to paste or attach it and skip Step 2 (still self-audit their script against the
failure modes and flag anything that breaks the format before moving on).
If Claude is writing it, ask for: brand name + spelling; product name; product category;
the creator's persona (age range, vibe, why they'd plausibly try this); the specific
skepticism/doubt they start with; the one moment that changes their mind; 1-2 concrete,
specific product details to mention (not superlatives); setting (bedroom / bathroom
mirror / car / porch); target length (~30-45s).
Either way, ask for: product reference image (path or URL).
If the user already attached the product image or gave a product URL, don't ask again.

## Step 2 — Write the script (skip if user supplied their own)
Follow Section 3 of the style-bible exactly — 6 beats.
Rules: first-person conversational; contractions and natural filler; no brand-speak or
superlatives; state the doubt before the win; specific over hype; short sentences, one
thought per line; read aloud test.
Save as [run_dir]/script.txt — creator VO only, timestamped by beat.
Self-audit against the failure modes before saving.

## Step 3 — Build per-scene prompts
Save as [run_dir]/scene_prompts.json. Default split mirrors the beats (one per beat;
shorter cutdown = 4 scenes: hook, try-on, reaction, CTA).
Each scene object has: scene, beat, duration_sec, aspect_ratio, tool ("fashion_tryon" or
"product_showcase" or "generate_video"), image_url, prompt, captions.
Rules: repeat the creator description verbatim every scene, only setting/action changes;
explicitly exclude cinematic/studio/color-grade language; product label/color described
for recognizability; avoid nudity/shower implications; name the setting per beat.

## Step 4 — Render (optional) — HARD WAIT, costs money
Ask before rendering. Either hand off the prompts, or render each scene via the connected
Arcads MCP tools. 9:16, natural light, audio optional. Confirm cost first.

## Step 5 — Hand off
Print: run dir path, all deliverable file names, the script in a code block, and the
reminder to stitch scenes, add the voice track, mute clip audio, and add plain captions
if wanted.

## Important behaviors
- Brand-agnostic. Prompt for inputs fresh every run.
- .txt for the script deliverable, .json for scene prompts.
- Read reference/style-bible.txt first.
- Refuse-and-redirect if the angle isn't a single believable creator with a specific doubt.
- Self-audit against the failure modes before saving.
- Hard wait before any paid render.
