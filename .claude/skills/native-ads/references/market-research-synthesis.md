# Market Intelligence Synthesis — Full Methodology

You are performing a structured market intelligence extraction across multiple CSV files containing raw comments, posts, and reviews scraped from platforms including Reddit, Amazon, Quora, Trustpilot, and YouTube. Read every piece of content across all files and produce **one unified synthesis report** — never a separate report per file.

Orient yourself first: you are not a marketer observing this person from a distance — you are inhabiting their perspective entirely, understanding the specific texture of their daily frustration, the weight they carry, the shame they don't say out loud, the exhaustion of trying things that didn't work. Read the data through Schwartz (desire already exists before the product), Halbert (the best copy sounds like a letter from someone who lived the exact problem), Hopkins (specificity is the only currency of believability), and Leach (most buying decisions are made before rational thought enters).

## Step One — Platform identification and structural mapping

Before extracting anything, identify which platforms are represented, and apply platform-specific reading logic:

- **Reddit**: Weight top-level posts most heavily for emotional rawness. Top-level comments with high upvote scores represent community validation. Nested replies often contain the most specific and unguarded language because the person feels buried enough to say the real thing. Note both thread level and score.
- **Amazon reviews**: Weight 1 and 2 star reviews most heavily for failed-solution data. 5 star reviews contain transformation language useful for the dream outcome. The review title often compresses the emotional truth most tightly.
- **Quora**: Question titles contain the problem as the person has consciously framed it. Answers contain attempted solutions and community-validated emotional experiences.
- **Trustpilot**: Emotionally extreme reviews in both directions contain the clearest language. Look at the gap between expectation and outcome as a signal of emotional load.
- **YouTube comments**: Short, high-like comments represent broadly shared emotional moments. Long comments represent someone who felt strongly enough to write past the friction of the comment box.

If a file's format differs from these, identify its columns and map them accordingly before proceeding.

## Step Two — Language collection rules

Apply these to every piece of content across every file:

1. **Do not paraphrase.** Do not summarize into cleaner language, do not translate into marketing language. Quote exactly as written, including grammatical errors, informal spelling, and profanity.
2. **Do not infer, do not assume.** Do not guess at feelings underneath what was said. If the emotional content isn't directly expressed in the text, it does not get included — except under the shame detection protocol (Step Three), which has its own rules.
3. A piece of language is only evidence for an emotional tension if that tension is **linguistically present in the text itself**. A clinical symptom description is not evidence of shame. A practical dosage question is not evidence of hopelessness. The emotion must be in the words.
4. When the same emotional expression recurs across posts/platforms, note the frequency — one Reddit comment carries less weight than a pattern across twelve posts and two platforms.
5. Distinguish original posters from commenters. Original posts tend to be more emotionally raw (the person is *in* the problem); comments are often more normalized (the commenter is slightly removed). Weight original-post language more heavily for emotional intensity.
6. Treat upvote counts and review helpfulness votes as community validation signals — note high-validation quotes separately.

## Step Three — Shame detection protocol

Shame is rarely stated directly ("I am ashamed of this" almost never appears). Apply these four patterns, all requiring direct textual evidence — never speculative:

1. **Minimization before disclosure** — framing something as small/silly immediately before revealing something clearly not small to them. Look for "probably sounds stupid but," "this might be dumb," "I know this is minor," "not sure if this counts," followed by a disclosure that contradicts the minimization.
2. **Anonymous confession language** — signals the person is saying here what they wouldn't say in a named context: "I've never told anyone this," "I can't say this to my partner," "I don't talk about this," "nobody knows how bad it actually is."
3. **Buried detail** — a significant emotional disclosure appearing at the end of a long post after context and credibility have been established, suggesting the person needed to build up to it.
4. **Self-deprecation that is not humor** — a joke about the problem that reads as deflection rather than lightness. The tell: the self-deprecating line contains more specificity than a real joke would need.

When shame is identified this way, quote the exact language and note which pattern triggered it.

## Step Four — Scoring methodology

For the five emotional tensions and three failed solutions, assign three scores:

- **Frequency score (1–10)**: how many distinct posts/comments/reviews express this tension or reference this failed solution. 1 = fewer than 5 sources, 10 = more than 50 sources.
- **Emotional intensity score (1–10)**: average intensity of the *direct language* used.
  - 1–3: calm, clinical, no emotional markers.
  - 4–6: frustration, disappointment, or worry, but controlled.
  - 7–9: desperation, grief, shame, rage, or hopelessness.
  - 10: a person at or past their limit — self-abandonment, surrender, crisis-level expression.
- **Combined score**: (frequency + intensity) / 2, rounded to one decimal. This is the ranking number.

If there is insufficient direct language to score something with confidence, do not assign a score — write instead: *"Insufficient direct language to score with confidence. Present in [X] sources but emotional load not clearly expressed in the text."*

## Step Five — Acute versus chronic language

For each major emotional tension, note whether it's expressed predominantly in **acute** language (writing from inside a crisis moment, happening right now) or **chronic** language (writing from exhausted long-term acceptance, desperation flattened into resignation). Both are useful but represent different advertising entry points.

## Step Six — Produce the report

Follow this exact structure. Do not deviate.

```
---
# MARKET INTELLIGENCE SYNTHESIS REPORT

**Sources analysed:** [list each platform and number of posts/comments read from each]
**Total data points:** [total individual posts, comments, and reviews read]
**Date of analysis:** [today's date]

---

## SECTION 1 — TOP 5 EMOTIONAL TENSIONS

Ranked by combined score, highest to lowest. For each:

### TENSION [NUMBER] — [NAME IN THEIR LANGUAGE, NOT MARKETING LANGUAGE]

| Score Type | Score |
|---|---|
| Frequency Score | [X] / 10 |
| Emotional Intensity Score | [X] / 10 |
| **Combined Score** | **[X.X] / 10** |

**Language type:** [Acute / Chronic / Mixed]

**Direct language extracted — exact quotes only:**
> [Quote 1 — platform and upvote/helpfulness score if available]
> [Quote 2]
> [Quote 3]
[Minimum 5 quotes per tension where data supports it. Maximum 12.]

**High-validation quotes** (significant upvote/helpfulness scores indicating broad resonance):
> [Quote with validation score noted]

**Psychoanalysis report:** 150–250 words analyzing this tension as expressed directly in the data. Do not infer beyond what the language shows. Note repeated words/constructions and what they indicate psychologically. Note whether the emotional expression is directed inward, outward at the world, outward at medical systems, or at the self. Note escalation or flattening patterns. Every claim must be supported by a quote above — if you can't support it with a direct quote, don't make the claim.

---
[Repeat for all 5 tensions]
---

## SECTION 2 — TOP 3 FAILED SOLUTIONS

Ranked by emotional load (distress, frustration, financial/time/hope loss directly expressed). For each:

### FAILED SOLUTION [NUMBER] — [NAME OF SOLUTION]

**Emotional load score:** [X] / 10
**How common:** [number of sources]

**What they tried exactly** (direct quotes):
> [Quote]

**Why the failure hurt** (direct quotes of emotional response):
> [Quote]

**The specific cost** — financial, time, hope, or physical cost, quoting language that shows this directly.

**Inconclusive flag:** if emotional load can't be determined with confidence, state this and explain what is/isn't present.

---
[Repeat for all 3 failed solutions]
---

## SECTION 3 — THE HARDEST MOMENT

The single most specific moment the problem hits hardest, per the data — not a time of day, the actual scene: where they are, what they're doing, who is present, what triggered it. 100–150 words, only detail directly supported by quoted language. If multiple distinct hard moments appear with roughly equal frequency/intensity, report the top two and note the data doesn't produce one clear answer.

---

## SECTION 4 — THE SHAME LAYER

Built entirely from the Step Three shame detection protocol — no shame that isn't linguistically present.

**Detection pattern used:** [which of the four]
**Direct language:**
> [Quote]

**What the language shows:** 75–100 words, every sentence supported by a quote above. If insufficient shame-language exists, state: *"The data does not contain sufficient direct shame-language to report this section with confidence. The following adjacent language may be relevant but cannot be classified as shame without inference:"* then list what's present.

---

## SECTION 5 — CROSS-PLATFORM TENSION MAP

If more than one platform is present, note whether the same tensions appear consistently across platforms or different platforms surface different expressions of the same problem. Factual and direct — only what the data shows.

---

## SECTION 6 — RAW LANGUAGE VAULT

Every high-utility phrase that doesn't fit neatly into the sections above but carries strong emotional charge, unusual specificity, or feels highly native to the community. Quote exactly, don't edit or clean up.

---
*End of report. All claims in this report are supported by direct language from the source files. Nothing has been inferred, assumed, or constructed from outside the data.*
```
