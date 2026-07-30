# style-3d — the signature Zack look

This is the visual backbone of the whole channel. Every still and every video
block pulls from the exact same formula so the model renders the *same world*
every time instead of drifting scene to scene. That's what makes recurring
characters, props, and locations read as consistent — the model isn't
"remembering" anything, it's being handed the same description again.

## THE STYLE FORMULA (byte-identical, paste into every prompt)

Copy this block verbatim into every `seedream_v5_pro` and `gemini_omni` prompt
in Phases 5 and 6. Do not paraphrase it — even small wording changes shift the
render enough to break consistency.

```
STYLE: glossy stylized-realistic 3D render, feature-animation quality
(Pixar/DreamWorks-adjacent proportions, higher material fidelity than
cartoon), physically-based rendering on every surface — brushed metal with
true reflections, roughened stone and dust, woven cloth with visible thread,
skin with subtle subsurface scattering. LIGHT: single warm key sun (golden-
hour amber, low hard-edged shadows) against a saturated cobalt-blue sky, soft
cool bounce fill on shadow sides, subtle rim light separating subject from
background. LENS: 35-50mm equivalent framing on mediums/wides, 85mm-equivalent
compression on close-ups, shallow-ish depth of field falloff behind the hero
subject, faint natural vignette. COLOR: warm highlights against cool shadows,
rich and saturated but not neon - the only neon in frame is baked green/red
annotation glow, never the environment itself. COMPOSITION: clean readable
silhouettes, generous headroom and footroom (top ~12% / bottom ~12% of frame
kept uncluttered) for a 9:16 vertical crop.
```

## Character design language
- Slightly stylized proportions — believable anatomy, not photoreal, not
  flat-cartoon. Faces stay expressive and readable at thumbnail size.
- Every recurring character keeps one unmistakable silhouette cue (a hat, a
  hairline, a build, a scar) that survives even a 1-second glance.
- Costume/prop materials always named explicitly (bronze, linen, oak, etc.) so
  PBR has something to grab onto — "a sword" renders inconsistently across
  generations, "a leaf-bladed bronze sword with a worn leather grip" doesn't.

## Environment design language
- Environments are dressed sets, not empty boxes — foreground, midground, and
  a hazy background layer for depth, even in a 10s block.
- Keep the same time-of-day (the warm sun / cobalt sky pairing above) across
  every environment plate for one video. Don't let one block go overcast.

## Annotation grammar (baked in-world, never on-screen text)
Annotations are rendered by the video model as glowing geometry, not
typography. Every prompt that needs one should spell out shape + color +
behavior explicitly:
- **Green** = "look here / here's how it works": a thin glowing neon-green
  outline hugging the exact edge of the part in question, or a glowing green
  arrow that draws itself toward the subject, held for the length of the shot.
- **Red** = "danger / physics / failure": a dashed glowing red line tracing a
  trajectory (falling debris, a strike path), or a glowing red crack that
  spiders across a surface, or a soft red impact burst (expanding ring, no
  screen flash) at the moment of contact.
- Never both colors on screen at the same time in the same shot — pick the one
  the beat is actually making.
- Annotations are geometry the camera can see, not a UI overlay: they must sit
  in 3D space on the actual object, so they hold up under a whip-pan or
  crash-zoom instead of sliding around like a sticker.

## Negative prompt (append to every Phase 5/6 prompt)
```
NEGATIVE: no on-screen text or captions, no logos or brand marks, no
watermarks, no photoreal human faces, no extra or malformed limbs/fingers,
no lip-sync mouth movement, no modern clothing or technology, no camera/UI
overlays, no color grading outside the warm-sun/cobalt-sky palette.
```

## Subject-bleed guard (see Phase 5 for when to use it)
The style key still is a *specific scene* with a *specific hero subject* in
it — when you hand its job_id to an environment-plate prompt as a style
reference, the model tends to also copy the subject into the empty location,
which contaminates every asset sheet that's supposed to be people-free. Use
the guard wording from Phase 5 (`ENVIRONMENT SHEET — EMPTY LOCATION PLATE...`
+ the explicit `ABSOLUTELY NO {style-key subject}` line) on every environment
plate, and check the result before moving on — it's cheaper to catch here
than after six blocks reference a contaminated plate.

## Per-asset-type prompt skeletons
**Person sheet:** `{STYLE FORMULA} — CHARACTER SHEET, {name/role}, full body,
front 3/4 view, neutral flat grey backdrop, arms slightly away from body,
{costume/material description}, {silhouette cue}. {NEGATIVE}`

**Object/prop sheet:** `{STYLE FORMULA} — PROP SHEET, {object}, isolated on
neutral backdrop, no scene, no hands, {material description}. {NEGATIVE}`

**Environment sheet:** `{STYLE FORMULA} — ENVIRONMENT SHEET, EMPTY LOCATION
PLATE, take only the render style and palette from the reference image, NOT
its subject, {location description}, dressed set, no people, no animals.
ABSOLUTELY NO {style-key subject}, NO people, NO animals. {NEGATIVE}`
