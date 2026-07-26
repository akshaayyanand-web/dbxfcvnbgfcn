# Personal Video Editing Studio

A conversation-driven video pipeline for Claude Code, built by vendoring two
agent-native editing tools as project skills:

- **[video-use](https://github.com/browser-use/video-use)** (MIT) — raw-footage editor.
  Transcribes, cuts, color grades, removes fillers/silence, burns subtitles, and
  produces `final.mp4` from raw takes, driven entirely by conversation.
- **[hyperframes](https://github.com/heygen-com/hyperframes)** (Apache-2.0) — motion
  graphics / HTML-to-MP4 rendering engine. Builds titles, lower-thirds, captions,
  overlays, charts, and other motion graphics as deterministic HTML compositions,
  then composites them into the edit.

Together: **video-use ingests and cuts the footage, hyperframes designs and
renders the motion graphics layer, video-use composites the overlays back in
and ships `final.mp4`.**

## Pipeline

```
raw footage
   │
   ▼
[video-use]  transcribe (ElevenLabs Scribe) → pack transcript → converse on strategy
   │         → build EDL → extract/concat/grade clips
   │
   ▼
[hyperframes] design + render motion graphics slots (titles, lower-thirds,
   │          captions, charts, logo reveals, transitions) as HTML → MP4/transparent overlay
   │
   ▼
[video-use]  composite overlays (PTS-aligned) → burn subtitles LAST → self-eval
   │         at every cut boundary → iterate
   ▼
final.mp4
```

`video-use`'s `SKILL.md` explicitly treats HyperFrames as one of its pluggable
animation engines for the "generate overlay animations" step (alongside
Remotion and Manim), invoked via `npx --yes hyperframes ...` inside a slot
directory — so the two repos are already designed to compose this way.

## What's installed

Skills live under `.claude/skills/` and are auto-discovered by Claude Code
when this repo is the working directory:

| Skill | Role |
|---|---|
| `video-use` | Full editing skill: transcribe, cut, grade, subtitle, composite. Includes the vendored `manim-video` sub-skill for math/code animations. |
| `hyperframes` | Router/entry point for any "make/edit/animate a video" request. Reads project state, runs the intent interview, routes to a workflow. |
| `hyperframes-core` | Composition authoring contract (HTML/CSS timing model, `data-*` attributes). |
| `hyperframes-animation` | Motion vocabulary, animation rules/blueprints (GSAP, CSS/WAAPI, Lottie, Three.js). |
| `hyperframes-creative` | Design/creative direction rules for compositions. |
| `hyperframes-cli` | `hyperframes` CLI usage: init, preview, render, lint, check, snapshot. |
| `hyperframes-keyframes` | Keyframe-driven animation authoring. |
| `hyperframes-registry` | Reusable composition/block registry. |
| `media-use` | Resolving/sourcing media assets (search, stock, generation) for compositions. |
| `watch` | Watch/analyze any video (URL or local) — captions + frames + transcript — for Q&A about footage. Useful for reviewing source material or a rendered cut. |

This is the **core hyperframes set** (as recommended by its own docs — the
router installs everything else on demand). Specific creation workflows
(`motion-graphics`, `general-video`, `embedded-captions`, `talking-head-recut`,
`product-launch-video`, `music-to-video`, `slideshow`, `faceless-explainer`,
`pr-to-video`, `figma`, `remotion-to-hyperframes`) are **not vendored** — the
`hyperframes` router pulls the one it needs at run time via
`npx hyperframes skills update <workflow>` so they never go stale. If you want
all 19 vendored locally instead, run:

```bash
npx skills add heygen-com/hyperframes --all --full-depth
```

## Setup

1. **ffmpeg + ffprobe** on `$PATH` (hard requirement for video-use).
   ```bash
   # Debian/Ubuntu
   sudo apt-get update && sudo apt-get install -y ffmpeg
   ```
2. **Python deps for video-use**:
   ```bash
   cd .claude/skills/video-use
   command -v uv >/dev/null && uv sync || pip install -e .
   ```
3. **ElevenLabs API key** (Scribe transcription — word-level timestamps + diarization):
   ```bash
   printf 'ELEVENLABS_API_KEY=%s\n' "$KEY" > .claude/skills/video-use/.env
   chmod 600 .claude/skills/video-use/.env
   ```
   Never commit this file (already covered by repo `.gitignore`/should be added if missing).
4. **Node.js 22+** for hyperframes rendering (Puppeteer/Chrome + ffmpeg). This
   environment already has Chromium at `/opt/pw-browsers`. No API key needed
   for local rendering — `npx hyperframes init/preview/render` works out of the box.
5. Optional: `yt-dlp` for pulling source footage from URLs.

## Usage

Drop raw footage into a folder, `cd` into it, start `claude`, and say something
like:

> "edit these into a launch video"

or, for a standalone motion graphic:

> "make me a 10s animated logo reveal"

Claude reads `SKILL.md` for `video-use` (editing) and/or `hyperframes` (motion
graphics/animation) automatically, converses on strategy, executes, self-evaluates,
and iterates. All session outputs land in `<footage_dir>/edit/` — never inside
the skill directories.

## License notes

- `.claude/skills/video-use/` is vendored from browser-use/video-use, MIT licensed (`LICENSE` included).
- `.claude/skills/hyperframes*` and `.claude/skills/media-use/` are vendored from heygen-com/hyperframes, Apache-2.0 licensed (`LICENSE` included under `hyperframes/`).
