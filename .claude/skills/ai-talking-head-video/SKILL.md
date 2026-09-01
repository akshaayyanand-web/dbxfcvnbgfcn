---
name: ai-talking-head-video
description: Create realistic AI talking-head video generation prompts from a reference image and full script. Use this skill when the user provides or plans to provide a reference image and script for AI-generated talking-head/UGC videos. The workflow uses the reference image as the visual identity, generates directly via image-to-video/lip-sync without requiring a separately generated voiceover, analyzes emotional delivery and pauses, and splits scripts into natural 4–10 second clips with a strong preference for 8–10 seconds. Never cut dialogue mid-sentence or mid-thought.
---

# AI Talking-Head Video Generation Skill

## Purpose

Create ready-to-use prompts for realistic AI talking-head videos using:

- A user-provided reference image
- A user-provided full script
- Image-to-video/lip-sync generation
- Natural emotional performance direction
- Short clip segmentation for easier generation and editing

The final result should feel like a real person naturally recording a talking-head/UGC video, not an AI avatar reading a script.

---

# 1. INPUT WORKFLOW

The user will provide two primary inputs:

1. **Reference image**
2. **Full talking-head script**

Treat the reference image as the primary visual source for the speaker.

Treat the supplied script as the source of truth for dialogue.

Do not unnecessarily rewrite, paraphrase, shorten, or reorder the script.

---

# 2. REFERENCE IMAGE

Use the reference image to preserve the speaker's visual identity and recording environment.

Maintain:

- Facial identity
- Face shape and proportions
- Age and general appearance
- Hair style and color
- Skin tone
- Natural skin texture
- Makeup
- Clothing
- Accessories
- Background
- Environment
- Camera angle
- Framing
- Lighting
- Overall visual style

The generated person should look like the same person from the reference image.

Think:

> "The exact person in the reference image is now naturally speaking to the camera."

Do not redesign the character unless specifically requested.

If multiple clips are generated, maintain visual continuity across every clip.

---

# 3. DIRECT IMAGE-TO-VIDEO / LIP-SYNC WORKFLOW

Do NOT generate a separate voiceover/audio file first unless the user explicitly asks for one.

The default workflow is:

**Reference image + dialogue + performance direction → image-to-video/lip-sync generation**

Do not default to:

**Reference image → separate voiceover → lip-sync**

The generated video should directly incorporate the supplied dialogue and produce natural mouth movement synchronized to the speech.

---

# 4. SCRIPT ANALYSIS BEFORE GENERATION

Before creating video prompts, analyze the entire script.

Identify:

- Natural sentence boundaries
- Complete thoughts
- Topic changes
- Emotional beats
- Important claims
- Punchlines
- Questions
- Emphasis points
- Natural breathing points
- Natural pauses
- Changes in delivery intensity

Do not split the script mechanically by word count.

Split according to natural speech and meaning.

---

# 5. SCRIPT SEGMENTATION — CRITICAL RULE

Break the full script into individual video clips.

### Preferred duration

Default to:

**8–10 seconds per clip**

However, these durations are also valid:

- 4 seconds
- 6 seconds
- 8 seconds
- 9 seconds
- 10 seconds

Choose the duration based on the natural length of the dialogue.

### Priority order

Always prioritize:

**Complete sentence/thought → natural speech → realistic performance → target duration**

Do not force dialogue into an arbitrary duration.

---

# 6. NEVER CUT OFF A SENTENCE

This is an absolute rule.

Every generated clip must end on:

- A complete sentence, or
- A complete natural thought

Never end a clip:

- Mid-sentence
- Mid-word
- Mid-phrase
- Immediately before the conclusion of a thought
- At an unnatural grammatical boundary

Bad:

> "The reason these lashes don't last is because the bond—"

Good:

> "The reason these lashes don't last is because the bond isn't designed to hold through a full day."

The clip should end naturally after the completed thought.

This rule takes priority over hitting exactly 8 or 10 seconds.

---

# 7. DURATION LOGIC

Determine duration AFTER deciding where the natural clip boundary is.

For each section:

1. Identify a complete thought.
2. Estimate natural spoken duration.
3. Choose the closest practical clip length.
4. Prefer 8–10 seconds when the content naturally supports it.
5. Use 6 seconds when the thought naturally finishes around 6 seconds.
6. Use 4 seconds when the thought is very short.
7. Never add filler to reach a target duration.
8. Never unnaturally speed up speech to meet a target.
9. Never cut off a sentence to meet a target.

Examples:

### Approximately 8 seconds

Dialogue:
"That's not a lash problem, that's a calendar and a budget problem."

Duration:
8 seconds

### Approximately 10 seconds

Dialogue:
"The bond on a lot of these budget kits just isn't made to hold through a full day."

Duration:
10 seconds

### Approximately 6 seconds

Dialogue:
"And that's where the problem starts."

Duration:
6 seconds

### Approximately 4 seconds

Dialogue:
"And honestly, it shows."

Duration:
4 seconds

These are examples only. Determine the actual duration from the supplied script.

---

# 8. CLIP CONTINUITY

Although the script is split into multiple clips, the final sequence should appear to be one continuous recording.

Maintain consistency in:

- Speaker identity
- Clothing
- Hair
- Makeup
- Accessories
- Background
- Lighting
- Camera angle
- Camera distance
- Framing
- Overall visual quality

Avoid introducing visual changes between clips unless specifically requested.

---

# 9. EMOTIONAL PERFORMANCE

Analyze every clip individually.

Do not apply one emotion to the entire script.

For each clip determine:

- Emotion
- Emotional intensity
- Facial expression
- Speaking pace
- Vocal emphasis
- Pause placement
- Eye behavior
- Head movement
- Body language

### Problem / pain point

Use:

- Slight concern
- Serious but natural expression
- Subtle eyebrow movement
- Direct eye contact
- Slightly slower delivery

### Surprising statement

Use:

- Brief eyebrow raise
- Slight expression change
- Short pause
- Stronger emphasis on the key phrase

### Solution

Use:

- Calm confidence
- Relaxed facial muscles
- Clear delivery
- Slightly more positive expression

### Exciting result

Use:

- Subtle smile
- Increased energy
- Brighter expression
- Slightly more animated delivery without overacting

### Conversational explanation

Use:

- Relaxed expression
- Natural blinking
- Small head movements
- Casual pacing
- Authentic conversational rhythm

---

# 10. NATURAL PAUSES

Use pauses strategically.

Good pause locations include:

- Before an important claim
- After an important claim
- Before a punchline
- At natural punctuation
- During an emotional beat
- Before revealing a result
- At natural breathing points

Example:

> "That's not a lash problem... that's a calendar and a budget problem."

The pause should create emphasis.

Do not overuse pauses.

The person should sound like they are genuinely speaking rather than mechanically following punctuation.

---

# 11. NATURAL HUMAN IMPERFECTIONS

The speaker should behave like a real person.

Include subtle:

- Blinking
- Breathing
- Eye movement
- Micro-expressions
- Small head movements
- Natural mouth movement
- Minor posture adjustments
- Subtle facial asymmetry
- Small conversational gestures when appropriate

Avoid exaggerated behavior.

Do NOT introduce:

- Excessive blinking
- Constant smiling
- Large eyebrow movements
- Excessive hand gestures
- Large head movements
- Robotic facial expressions
- Frozen expressions
- Overacting

---

# 12. CAMERA DIRECTION

Preserve the camera style from the reference image.

If the reference looks like iPhone/UGC footage, maintain that aesthetic.

Prefer:

- Eye-level framing
- Natural perspective
- Realistic camera distance
- Stable or subtly handheld camera movement
- Natural framing
- Minor camera imperfections when appropriate

Avoid:

- Cinematic zooms
- Dramatic camera movements
- Camera rotations
- Floating-camera movement
- Excessive depth of field
- Artificial transitions
- Unnecessary reframing

The camera should feel like a real person is recording the speaker.

---

# 13. BACKGROUND AND LIGHTING

Preserve the reference environment.

Do not randomly change:

- Room
- Wall
- Furniture
- Props
- Background
- Lighting direction
- Lighting intensity
- Color temperature

Keep lighting realistic and consistent.

Avoid the typical AI look of:

- Plastic skin
- Excessive smoothing
- Artificial shadows
- Unrealistic highlights
- Inconsistent lighting between frames

---

# 14. LIP SYNC

Lip synchronization is a high-priority requirement.

The mouth must accurately correspond to the supplied dialogue.

Prioritize:

- Correct mouth shapes
- Natural lip movement
- Realistic jaw movement
- Correct timing
- Natural transitions between words
- Natural mouth behavior during pauses
- Realistic teeth visibility
- Natural cheek movement

Avoid:

- Rubber-like lips
- Mouth stretching
- Lip-sync drift
- Mouth movement during silence
- Teeth artifacts
- Facial warping
- Unnatural jaw movement

---

# 15. SCRIPT-TO-PERFORMANCE BREAKDOWN

For each clip, determine:

**Dialogue**
- Exact dialogue assigned to the clip.

**Duration**
- 4, 6, 8, 9, or 10 seconds as appropriate.

**Emotion**
- The primary emotional state.

**Intensity**
- Low, medium, or high.

**Pacing**
- Slow, natural, or slightly fast.

**Pause placement**
- Exact moments where pauses should occur.

**Facial expression**
- How the face should react.

**Eye contact**
- Maintain natural direct-to-camera eye contact.

**Head movement**
- Subtle and contextually appropriate.

**Body language**
- Restrained, believable gestures.

**Emphasis**
- Identify words or phrases that should receive additional emphasis.

---

# 16. VIDEO PROMPT STRUCTURE

For every clip, create a detailed image-to-video prompt containing:

## SUBJECT

Preserve the exact person from the reference image.

## APPEARANCE

Do not change:

- Identity
- Face
- Hair
- Clothing
- Makeup
- Accessories
- Age
- Physical characteristics

## ENVIRONMENT

Preserve the reference setting and background.

## CAMERA

Describe:

- Framing
- Camera position
- Camera distance
- Stability
- Natural movement

## PERFORMANCE

Describe how the person physically delivers the dialogue.

## EMOTION

Describe the emotional state and intensity.

## FACIAL EXPRESSION

Describe the relevant facial changes.

## EYE CONTACT

Maintain believable direct-to-camera eye contact with natural eye movement.

## BODY LANGUAGE

Use subtle natural movement.

## PAUSES

Describe important conversational pauses.

## DIALOGUE

Use the exact dialogue assigned to the clip.

Do not paraphrase it.

## LIP SYNC

Require accurate natural synchronization between speech and mouth movement.

## REALISM

Require:

- Natural skin
- Realistic facial movement
- Natural blinking
- Natural breathing
- Realistic eye movement
- Believable micro-expressions
- Natural human imperfections

## DURATION

State the intended duration clearly.

---

# 17. NEGATIVE INSTRUCTIONS

Include appropriate negative instructions such as:

- No identity changes
- No face morphing
- No facial distortion
- No facial warping
- No different person
- No hairstyle changes
- No clothing changes
- No makeup changes
- No background changes
- No lighting changes
- No unnatural eyes
- No excessive blinking
- No frozen facial expression
- No rubber lips
- No incorrect lip sync
- No mouth movement during pauses
- No teeth artifacts
- No plastic skin
- No excessive skin smoothing
- No AI-avatar appearance
- No excessive gestures
- No overacting
- No unnatural head movement
- No unnatural body movement
- No camera distortion
- No dramatic camera movement
- No unnecessary zoom
- No visual discontinuity

---

# 18. OUTPUT FORMAT

When the user provides the reference image and script, first segment the script and then create the prompts.

Use this structure:

# SCRIPT SEGMENTATION

## Clip 1
**Duration:** 8 seconds  
**Dialogue:** "..."  
**Emotion:** ...  
**Intensity:** ...  
**Pacing:** ...  
**Pause:** ...  
**Facial expression:** ...  
**Body language:** ...  
**Emphasis:** ...

## Clip 2
**Duration:** 9 seconds  
**Dialogue:** "..."  
**Emotion:** ...  
**Intensity:** ...  
**Pacing:** ...  
**Pause:** ...  
**Facial expression:** ...  
**Body language:** ...  
**Emphasis:** ...

Continue until the complete script is covered.

Then provide:

# IMAGE-TO-VIDEO PROMPTS

## Clip 1 — [Duration]

[Detailed ready-to-use generation prompt]

## Clip 2 — [Duration]

[Detailed ready-to-use generation prompt]

Continue for every clip.

---

# 19. COMPLETENESS CHECK

Before finalizing, verify:

### Script
- Every part of the original script is included.
- Script order is unchanged.
- Dialogue has not been unnecessarily rewritten.
- No important line has been omitted.

### Segmentation
- Clips are generally 4–10 seconds.
- 8–10 seconds are preferred where natural.
- 6-second clips are allowed.
- 4-second clips are allowed.
- Every clip ends on a complete sentence or complete thought.
- No clip ends mid-sentence.
- No clip ends mid-word.
- No artificial filler was added.

### Performance
- Each clip has appropriate emotional direction.
- Pauses are natural.
- Facial expressions match the meaning.
- Delivery feels conversational.
- Eye contact feels human.
- Body language is restrained and believable.

### Visual consistency
- Same identity across clips.
- Same clothing.
- Same hair.
- Same makeup.
- Same environment.
- Same lighting.
- Same camera style.

### Realism
- Natural blinking.
- Natural breathing.
- Realistic facial movement.
- Accurate lip sync.
- No obvious AI-avatar behavior.

---

# 20. CORE PRINCIPLE

The final video should feel like an authentic person casually recording a talking-head video.

Think:

> "I'm talking naturally to one person sitting behind the camera."

Not:

> "I'm performing a perfectly polished advertisement."

The objective is:

**Realistic + conversational + emotionally appropriate + naturally paced + accurately lip-synced + visually consistent.**

The individual clips should be easy to generate separately and then stitch together into one continuous-looking talking-head video.

The most important segmentation rule is:

**Never sacrifice a natural sentence ending just to hit a specific duration.**

If the natural section is approximately 8 seconds, make it 8 seconds.

If it is approximately 6 seconds, make it 6 seconds.

If it is approximately 4 seconds, make it 4 seconds.

If it naturally requires 9–10 seconds, use 9–10 seconds.

**Complete thought > natural speech > realistic performance > exact duration.**
