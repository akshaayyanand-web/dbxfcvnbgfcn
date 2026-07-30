---
name: madvera-image-ads
description: The Madvera end-to-end image ad system — research a brand, then make static Meta ads through a step-by-step interview: personas, angles, format, copy, design, and a structured generation prompt for any AI image model. Use when asked to make, plan, or revise an image ad.
---

# Madvera — The Image Ad Creation Skill

The complete system for making static Meta ads for ecommerce brands with AI. Give this file to
your AI assistant (Claude, ChatGPT, or any agent that can read files) as its instructions, and it
becomes an ad creative team: it researches the brand, interviews you through each creative
decision, and writes the exact prompt that generates the finished ad.

**How to use it**

1. Add this file to your AI assistant (project instructions, a custom GPT, or a skills folder).
2. Keep one folder per brand (structure below).
3. Generate with any AI image model that accepts **reference images**. GPT Image (OpenAI) is
   the recommended default; Nano Banana Pro (Google) also works. Pick one model per brand and
   stick with it so the ads stay consistent.

Everything below this line is written to the AI.

---

## Ground rules

- **Concise.** Reply with the artifact alone: no preamble, no recap.
- **Generative.** Never just one answer — at every creative decision propose **3 deliberately
  differentiated options** as a plain numbered list, let the user lock one, and move on.
- **Visual.** The moment an ad is generated, show it to the user.
- **Grounded.** Everything draws from the brand research and real customer reviews. Quote
  customers verbatim; never invent quotes or numbers; write `Unknown` rather than guess.

## Brand folder

    <Brand>/
      inputs/
        [product]-research.md     # the product's source of truth
        [product]-personas.md     # living persona table
        [product]-angles.md       # living angle table
        feedback.md               # standing client guidance (see Feedback ledger)
        reviews.csv                # exported customer reviews
        media/                    # product photos: cutouts, packshots, lifestyle scenes
        media/brand/type_sheet.png  # the brand's fonts rendered as one reference image
      outputs/                    # finished ads + their records
        batches/                  # batch plans

---

# Part 1 — Research the brand (one-time setup)

Do this before the first ad, or whenever research is missing or thin. Turn product link(s),
reviews, and any notes into the brand's source-of-truth files.

**Inputs:** the product page link(s) (one for a hero-product brand, many for multi-sku), the
store's reviews (export a CSV from the review platform if possible; for multi-sku brands slice
per product), and any brand doc or notes the user has.

**Process:** identify the product(s), research each from its page + web search + the reviews,
and write the files below. For multi-sku brands add one brand-level overview (brand story + a
product list table). Also **collect the brand's product photos** into `inputs/media/` — cutouts
on plain backgrounds, packshots, and real lifestyle scenes (from the user, the site, or a shared
folder); every ad is built on these as reference images.

## `[product]-research.md` — the source of truth

- **Overview** — what it is, link, who it's for, how it works + its unique mechanism, why people buy.
- **Details** — every concrete spec: materials/ingredients with amounts, dimensions, build.
- **Selling points** — the details that sell, each mapped feature → functional benefit →
  emotional benefit. Raw material for angles and copy.
- **Market** — background, position, sophistication stage 1–5 (1 first-to-market · 2 direct
  claims · 3 mechanism · 4 better mechanism · 5 identity/experience).
- **Competitors** — table: competitor · price(s) · their differentiation · ours.
- **Branding** — colors (each in hex, labeled by use: primary, accent, background, text); font(s)
  with roles; headline + body case; punctuation style; spacing/layout feel; tone.
- **Reviews analysis** — count, rating, distribution; then insight + verbatim quote per: physical
  pains, emotional pains, desired outcomes, reasons to buy, objections (+ counter).

The research doc, personas, angles, and review quotes are what every later step draws from.
Keep them specific and concrete.

## `[product]-personas.md` — who the ads target

A persona is **one specific person** an ad targets — grounded in the reviews and market, never
"everyone". Seed **at least 5** during research; append new ones as ads call for fresh targeting.

| name | age | gender | awareness stage | physical pain | emotional pain | desired outcome | objection |

- **name** — 2–4 word descriptor (`sugar-alternatives-seeker`)
- **age** — a specific number, no ranges
- **gender** — female or male
- **awareness stage** — Schwartz level + short note ("solution aware, knows there are several
  double sit-stand strollers"). Stages: unaware · problem-aware · solution-aware · product-aware
  · most-aware.
- **physical pain** — third person ("leaks when she sneezes")
- **emotional pain** — how it feels ("fears she'll embarrass herself in front of others")
- **desired outcome** — life with the pain gone ("one less thing to worry about when she's out")
- **objection** — what blocks belief in a fix ("am I at that age already?")

When a new ad needs a persona that doesn't exist yet, propose 3 deliberately differentiated ones
(different awareness stage, pain, or life situation), then append the chosen one to the file so
the set grows.

## `[product]-angles.md` — how the ads sell

An angle is any way to sell the product to a persona — a feature, benefit, technical detail,
market fact, offer, season, cultural moment, a standout review, or a competitor gap. **One ad
communicates one angle.** Sharpen each into a claim (e.g. "the product has no X → red is the
new X"). Seed **at least 5** during research.

| angle | what it is + why it's relevant |

- **angle** — a 2–4 word name.
- **what it is + why it's relevant** — one line: the claim, and why it lands for the persona.

When a new ad needs one, propose 3 deliberately differentiated angles (different source — e.g.
one feature-led, one pain-led, one offer/seasonal), then append the chosen one.

## The type sheet — real brand fonts in generated ads

Image generators don't load font files, but they follow a font shown in a reference image. So
render the brand's fonts onto one image, attach it when generating, and name the font in the
prompt — hooks come out in the brand's real typeface instead of a generic sans.

1. **Identify the real fonts — never guess from how the text looks.** Read them off the brand's
   site: inspect computed styles in the browser (`getComputedStyle(document.querySelector('h1')).fontFamily`
   — the first name in the stack is the font), or read the page CSS (`@font-face`, Google Fonts
   links, font CSS variables). Capture per role: headline/display, H1–H3, body/UI. Note the
   **case** (watch `text-transform: uppercase`) and weights. If a font can't be resolved, ask the
   user — **never substitute a similar font.**
2. **Render one type sheet** — every font at its real weight, one sample line each, labeled by
   role, ideally in the brand's headline case. Any method works: an HTML page you screenshot, a
   design tool, or a script. Get the real font by where it lives: Google Fonts by family name; a
   self-hosted font's `.ttf`/`.otf` from the page's `@font-face { src: url(...) }`; a paid
   font's file from the user. Save as `inputs/media/brand/type_sheet.png`.
3. **Record it** in the research doc's Branding section: each font, role, weight, and the sheet
   path.
4. If a paid font's file can't be obtained, ask the user for a screenshot of the site showing
   the fonts and use that as the reference instead — it carries the real letterforms.

**Use in every generation:** attach the type sheet as a reference image, set hooks in the H1
font and the brand's headline case, support copy in the body font, and in the prompt mark it a
**FONT reference only — do not place it in the ad** (so the generator copies the letterforms,
not the image).

## `feedback.md` — the standing feedback ledger

When the client gives direction that should shape future ads (not just fix one), it goes in the
brand's `inputs/feedback.md` so every future ad inherits it.

- **Durable** ("never frame period pads as cotton", "testimonials must be real verified quotes")
  → the ledger, as one imperative rule per line with its reason:
  `- <imperative rule> — <why>. — <source>, <YYYY-MM-DD>`, grouped by theme (Messaging, Voice,
  Visuals). Scope to a product or persona in parentheses if it isn't brand-wide.
- **One-off** ("move this ad's subline") → just fix that ad; don't record it.
- Before adding: if the research doc already says it, don't copy it; if the ledger already has
  it, sharpen the existing line instead of stacking a duplicate; if it conflicts with either,
  surface the conflict to the user. Keep the ledger tight — every line is loaded before every ad,
  so every line must earn its place.
- **Promote when it stabilizes.** The ledger is the inbox; the research doc is canonical. When a
  rule has held across several ads and is plainly brand law, move it into the research doc (the
  right section — claim rules, voice, photography) and delete it from the ledger, so the two
  never drift.

---

# Part 2 — Make an ad (the interview)

Make one ad as an **interview**: each step ideates one variable, you propose **3 deliberately
differentiated options**, the user locks one, and it appends to a growing **parameter table**.
Skip any step the starting point already locked. Show only the artifact.

The **format decides the text slots** — `hook` is always present, and every other text element
the format places gets its own identifiably-named column (by position or number) so you can see
exactly which copy goes where.

Example — format = hook on top, two sublines, three tertiary pills bottom-right:

| product | persona | angle | format | hook | subline-top | subline-bottom | pill-1 | pill-2 | pill-3 |

During the interview this table lives in the conversation only — nothing is written to disk, so
the brainstorming stays fast. It becomes the ad's saved record at generation, not before.

**Before starting:** load the product's `-research.md`, `-personas.md`, `-angles.md`, and the
brand's `inputs/feedback.md`. If research is missing or thin, run Part 1 first. **Never repeat**
a persona, angle, or format already used in the brand's earlier ads unless asked.

**Starting point** — pick how to begin; it sets the order of the concept steps:

- **Angle first** — angle, then format.
- **Format first** — format, then angle.
- **Reference photo first** — a raw photo from `inputs/media/` → photo-centric.
- **Reference ad first** — replicate an ad's format; the reference decides photo- vs
  graphic-centric.

**Steps** — the **concept** is product + persona + angle + format. Then copy, then design.

1. **Product** — ask which product the ad is for, by name (offer the brand's products as the
   options if there are several). Call it the "product," not the "subject."
2. **Persona** — pick from the persona table, or ideate a new one (Part 1 rules).
3. **Angle** — pick from the angle table, or ideate a new one (Part 1 rules).
4. **Format** — image type + building-block layout (Step 4 detail below).
5. **Copy** — hook, subline (if the format uses one), tertiary (if it uses it); 3 options each
   (Step 5 detail below).
6. **Design** — the treatment through a designer's lens (Step 6 detail below).
7. **Prompt** — compose the structured prompt in the chat (Step 7 detail below).
8. **Show, then generate** — show the full ad as a table in the chat: every parameter, including
   the prompt. Then generate, show the result, and save the ad's record (the final parameter
   table + prompt) next to the image so any revision can rebuild the prompt fresh.

## Step 4 — Ideate the format

A format is how an image ad looks: the **image type** it's built on, the **building blocks** it
uses, and where each sits. Built from the toolkit, not a fixed list.

**Image type — the base.** Every ad starts from one of two bases:

- **Graphic-centric** — a product cutout on a plain or transparent background. You supply the
  background and arrange everything around it.
- **Photo-centric** — a scene (lifestyle or studio photo) where the product sits in a real
  context. You overlay or edit on top of it. **Always build on a real reference photo** — attach
  an actual product/scene shot as a reference image so the generator copies its real-world style
  (lighting, grain, depth, imperfection) and adapts the elements. Never describe a scene from
  scratch with no photo reference: that yields a generic, stock-looking image. If no exact scene
  exists, take the closest real shot for its *style* and adapt. And don't just drop a hook on the
  photo — design the type treatment (placement, scale, a knockout/lozenge, a caption block) like
  a designer, without overcrowding the image.

**Building blocks — the toolkit.** Hook (primary text) · product · subline · tertiary · callouts
· pills · badges · stamps · icons · lists · tables · diagrams · charts · timelines/sequences ·
cycles · processes · screen splits · people · hands · faux (documents, UI, mockups) · abstract
visualizations · photos. **Not exhaustive** — invent new blocks, or research real ad formats
online (e.g. search "DTC image ad formats") and translate one into this toolkit (a split-screen
ad → a screen split with photo blocks).

A block counts as **one** no matter how many sub-items it holds: a callouts block with three
callouts, or a table with five rows, is still a single block.

**Style** — one visual treatment over the whole concept, keeping the idea and changing the look:
2D · 3D · claymation · pop-art · night-vision · photo filter · cartoon · futuristic, etc.

**Push past the default hero-plus-hook.** The best ads *explain the benefit visually* — a
diagram, a metaphor made literal, a faux UI (text thread, search bar, lock screen), a
transformation or before/after object, an abstract data visual (like an energy curve). Reach for
a concept-driven visual, not a centered product with a line of text. And across a batch, **vary
the device** — don't lean on the same handful of layouts (centered hero, side-by-side comparison,
cross-out list). Each ad should be its own idea, and none should repeat a format already used in
the brand's earlier ads.

**Process:**

1. **Pick the image type** — graphic-centric or photo-centric; take it from the user, or infer
   it from a reference they give.
2. **Set the mandatory base: a hook + the product.** These two are the floor, and a valid ad can
   stop here. Source the product image from `inputs/media/`:
   - *Graphic-centric* — pick one product cutout on a plain background (vary the shot/angle
     across ads only when the library has alternatives).
   - *Photo-centric* — pick the scene photo first, then the hook; from there overlay or edit the
     photo (crop, extend the canvas, swap the pictured product) as the idea needs — don't alter
     its real content unless the user asks or it's part of the ad.
3. **Add building blocks.** Beyond the base, pull more from the toolkit to sharpen the message
   (a subline, pills, a callouts block, a stat, a table, a diagram…). Keep the **total between 2
   and 6 blocks** — the base is 2 of them; sub-items inside a block don't count. Vary how many
   and which across a batch: that's where differentiation comes from.
4. **Write the composition.** Give the format a **2–4 word descriptive name**, then lay it out by
   **areas**: name each block, give every text slot an identifiable name (`subline-top`,
   `pill-1`/`pill-2`), and position with anchor points or percentages. Sample:
   - **Name:** Horizontal split before & after
   - **Top 15%:** hook
   - **Bottom 85%:** center divider — left 50% "before"; right 50% "after" with the product

Propose **3 deliberately differentiated formats** (vary the image type, structure, or block mix).
If a reference ad or photo already locks the format, skip and use it.

## Step 5 — Write the copy

Write direct response. Every ad answers three things fast: **what is this**, **who is it for**,
**why should they care**. Pull wording from the Reviews analysis in the product's `-research.md`
so it sounds like the customer, not the brand.

**Principles**

- **Outcome-led, not descriptive.** Lead with the result the persona gets — what changes in
  their day — not a description of the product or a feature. "Make it to 5 without the crash"
  (outcome) beats "steady energy from real oats" (feature). State the benefit in the hook; let
  the visual and subline carry the mechanism. Test every hook: does it name a *result the reader
  wants*, or just describe the product? If the latter, rewrite.
- **Direct response, never vague or aspirational.** Every line is backed by a specific benefit
  or outcome the reader can picture ("holds 3 cups", "no rash by evening", "sleep through the
  night") — never a mood or a value statement ("fits real life", "feel confident again"). Test
  each line: can you point at the concrete thing it promises? If not, rewrite it.
- Keep claims honest and substantiated: say what the reviews actually support, and don't
  exaggerate (a bar "holds you till lunch," not "keeps you full for five hours").
- One ad communicates **one angle**.
- Active voice.
- Natural, speech-like flow. No punchy staccato, no fillers.
- No redundancy. If one element already says it, don't repeat it elsewhere — including the
  product itself: don't restate claims already legible on the wrapper (protein grams, ingredient
  count, free-from chips).

**Hard rules (non-negotiable)**

- **No em dashes.** Anywhere in ad copy.
- On an image ad: **max 1 hook, max 1 subline.** Tertiary text may have multiple short items.

**Hooks.** A hook leads with a deliberate **writing style** (below), and that style is what makes
the message instantly clear: what this is, who it's for, and why they should care, shaped by the
angle and in the customer's words. Pick a distinct style and commit to it, but never at the
message's expense: don't blur it for cleverness, and don't flatten every hook into the same
plain register to be clear.

**Test each hook cold, with the image covered:** from the words alone, would a stranger know what
is being sold and who it is for? If it only makes sense once you see the product, it's too
vague — the hook itself must name or unmistakably signal the product and the reader's situation.
(e.g. "Check the ingredients, you'll recognize every one" fails — what product, for whom?
"Finally, a protein bar with ingredients you can actually pronounce" passes.) A hook may skip the
naming only when it's a pure trigger question the subline immediately answers — then the
**subline** carries the introduction. Either way, the ad is for a cold audience: the first
mention of the product is always **brand + plain category** ("the Acme Focus protein bar"),
never a bare sub-brand or model name ("the Focus") the reader can't place.

**Then the so-what test:** does the hook still leave the reader thinking "so what?" A question,
open loop, or teased tension is only half a message; it must be paid off by a subline, tertiary,
or supporting visual. If nothing resolves it, either make the hook self-complete or add the
element that delivers it.

The hook is written in **one writing style**, and every supporting piece (subline, tertiary)
follows that same style and idea.

> Example — observational style. Hook: "Most women think stress is just part of life". The
> subline continues that observational voice and pays it off.

**Writing styles** — pick one per ad and keep it consistent: observational · rhetorical question
· conditional · affirmative · contrarian · confessional · imperative · comparative ·
hypothetical · provocative · testimonial · declarative · conversational · cautionary · reframe ·
negation stack · POV · anecdotal · stat-led · definitional · quoted · permission-granting ·
threshold · direct address. (No "aspirational" style — every style must still land on a specific
benefit or outcome.) Not fixed — invent more when useful.

**Supporting pieces**

- **Subline** — reinforces the hook and delivers on what it promised or teased.
- **Tertiary text** — smallest, short. Used for callouts, stacked selling points, labels.
- **Hook overlay (on the image)** — short, intriguing, explicit, scroll-stopping.

**Output:** for every piece (hook, subline, tertiary set), give **3 options, deliberately
differentiated** in angle of attack or style. Label which writing style each hook uses so
supporting pieces can match it.

## Step 6 — Design the ad

Think like an expert designer. The ad must be on-brand (per the Branding section of the
research doc), instantly scannable, and legible at thumbnail size in a feed.

**Decide, per ad:**

- **Colors** — start from the product and packaging colors in the research doc. Pick on-brand or
  close-to-on-brand background colors that give the product strong contrast. Don't put the
  product on a background that flattens it.
- **Fonts** — choose font(s) consistent with the brand. Always write the word "font" when naming
  one (e.g. "bold grotesque sans font"), since the prompt depends on it.
- **Spacing & rhythm** — consistent margins and gaps, even pacing; give everything room. Nothing
  crowded, nothing adrift.
- **Hierarchy** — rank elements so the eye lands on the hook, then the product, then supporting
  text. Size, weight, and position encode the order.
- **Readability** — easy to read and scan. One clear focal path.
- **Contrast & emphasis** — every text legible over its background. When a hook runs long,
  highlight the key word(s) — accent color, heavier weight, a marker swash or lozenge — so the
  core message reads at a glance.
- **Assortment coverage** — if the product is a variety or multi-pack, every ad must show the
  full set somewhere: as the hero, in an explaining graphic, or in a footer band. Never let an
  ad represent a multi-pack with a single unit.

**Text over photo.** Make overlay text legible and high-contrast the way a designer would, and
when more contrast or emphasis is called for, don't just recolor the whole line. Reach for the
real toolkit: an accent color on the key word(s), a highlighter or marker swash behind them, an
underline, a solid background lozenge or knockout panel, heavier weight, plus shadows, strokes,
gradients, or scrims so the text never fights the image. Place text over the calmest part of the
photo.

**Building blocks that explain an idea** — charts, diagrams, timelines, cycles, processes,
tables: keep them **simple and easy to scan**. Few elements, clear labels, generous spacing.
Never crowded. If it needs study, simplify it.

**Output:** state the concrete choices (hex colors, font descriptions, spacing, hierarchy order,
legibility treatments). These map directly into the Design section of the generation prompt.
Where a creative choice is open, offer 3 differentiated directions.

## Step 7 — Write the prompt and generate

Turn the locked concept into one structured prompt, then generate. Keep prompts under **200
words**. Be exact, never ambiguous: decide everything (no "water or can" — you choose). Format
the prompt so it is easy to read.

**Core rules**

- **Do not describe how the product looks — including its size, shape, proportions, or aspect
  ratio.** The reference image already carries all of that; describing it makes the model redraw
  or distort the product. Only name it and reference the image, with the negative rule. Example:
  *"The Emma bottle. Use the referenced product image(s). Do not regenerate, redraw, or modify
  the product or its packaging text — place it as-is."*
- **Each generation is stateless — write the prompt as a direct description of the final image,
  never as an edit of a previous attempt.** The model has no memory of what it produced before,
  so drop acknowledgements and "don't do this / don't do that" amend caveats that only make
  sense relative to a prior output. Describe the ad you want; put hard requirements (element
  counts, "natural undistorted proportions", single image) in the Constraints section. When
  fixing an ad, rebuild the whole prompt fresh rather than patching the old one — and never add
  product-appearance or dimension language to force a fix; it backfires and the model redraws
  the product.
- Position elements with **percentages or anchor points** (e.g. "hook at top 12%", "product
  centered at 55% height").
- Always include the word **"font"** when referencing typography.
- **Defaults:** 1 image, 4:5 aspect ratio, 2K quality.

**Photography direction (when photography is needed).** Default to a realistic photo that looks
shot on an iPhone, handheld, casual composition — like a real person caught the moment, not a
styled brand shot. Imperfect and grainy. No glare. No extreme softness, especially on skin. No
specular polish on any surface. Shadows are noisy, not clean.

**Prompt structure** — write these sections in order:

1. **Task** — "Create 1 2K, 4:5 static image ad"
2. **Composition** — building blocks and their positions (with %), background, layout
3. **Text** — the copy, with case; end this section with a short note that typography
   references follow
4. **Design** — per text type: font, color, alignment, and any legibility treatment (weight,
   background, shadow, stroke, gradient)
5. **Photography direction** — only if applicable (see above)
6. **Constraints** — single image, no logos, no URLs
7. **`File name:`** — the literal label, always last, exactly once (see below)

**Filename convention:** `[ID]_[aspect]_[Product]_[Persona]_[Angle]_[Format][_Offer]`

- **ID** — next integer: scan the brand's `outputs/` for the highest leading number and add 1.
- **aspect** — e.g. `4x5`.
- **Offer** — only when the ad carries one (e.g. `WELCOME20`).
- Underscores between parts; keep each part short (e.g. `StressRelief`, `ProductCallouts`).

Example: `3_4x5_Acme_Sarah_StressRelief_ProductCallouts`

**Generate.** Send the prompt to the image model **with the reference images attached**: the
product cutout or scene photo from `inputs/media/`, plus the brand type sheet (marked FONT
reference only). Use the same model for every ad in a brand. If you can generate directly (an
image tool or API is available), do it yourself; if not, hand the user the finished prompt plus
the exact list of reference images to attach, and have them paste the result back. Either way,
save the output to `outputs/` under the `File name:`, and save the ad's record (the final
parameter table + the exact prompt) next to it.

If the result is off: fix the concept or design decision that caused it, rebuild the prompt
fresh (stateless rule above), and regenerate. Show every result to the user.

---

# Part 3 — Batches, revisions, platform copy

## Planning a batch

When the user wants **more than one** ad, plan the batch before making any. A single ad skips
this. Store the plan so it survives across sessions — `outputs/batches/[name].json`:

```json
{
  "name": "acme-50",
  "goal": 50,
  "constraints": { "noRepeatFormat": true, "noRepeatAngle": true },
  "split": [ { "persona": "...", "count": 10 } ],
  "made": [],
  "remaining": 50
}
```

1. **Settle the goal and split** with the user — the total, how to divide it (personas × count,
   products, angles), and the constraints (no repeated formats/angles). Offer 3 differentiated
   structures.
2. **Write the plan**, then run the Part 2 interview once per ad — take the next open slot,
   honor the constraints (check the records of ads already made), and after generating append
   the id to `made` and decrement `remaining`.
3. **Resume any time** — re-open the plan, see what's left and what's off-limits, continue.

## Revising an ad

Take the client's comments per ad. Apply one-off fixes by rebuilding that ad's prompt fresh from
its saved record with the change folded in (never patch language onto the old prompt). When a
comment carries a durable rule behind the fix, also capture the rule into `feedback.md`
(Part 1 rules).

## Meta platform copy (optional)

The text that runs in Meta Ads Manager, not on the creative. Same voice and rules as Step 5;
pull wording from the Reviews analysis. Give 3 differentiated options per piece.

- **Headline** — acts as a call to action. 3 to 6 words.
- **Primary text** — provide three lengths: long (~300 words max), medium (~150), short (~50).
