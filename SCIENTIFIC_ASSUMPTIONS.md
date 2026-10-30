# Scientific Assumptions and Limitations

Every important modelling choice in FLAME IN FREEFALL is listed here with an ID.
Code comments and reports refer to these IDs. If an assumption is violated for a
given experiment, the corresponding results must be flagged or not reported.

## 1. Quantity classes (never mixed without a label)

| Class | Meaning | Example |
|---|---|---|
| `direct_measurement` | Value recorded by an instrument in the original experiment | chamber pressure from a NASA record |
| `image_derived` | Measured from pixels of a 2-D image | contour area in px² |
| `calculated` | Computed from the above with a stated model | radius in mm, equivalent volume, dr/dt |
| `heuristic` | Score for ranking/flagging, not a physical quantity or probability | `confidence`, `segmentation_quality` |
| `predicted` | Output of a machine-learning model | predicted extinction time (not built yet) |
| `simulated` | Produced by a generator or simulation | everything from `backend/vision/synthetic.py` |

## 2. Computer vision

**A-CV-1: Projection.** A camera records a 2-D, line-of-sight-integrated image of
a 3-D luminous region. All geometry is measured on that projection.

**A-CV-2: Primary size measure.** The flame size is the *area-equivalent radius*
`r = sqrt(A/π)`, where `A` is the pixel count of the filled external contour.
Using the pixel count instead of the polygon area avoids a −0.5 px bias. The
minimum enclosing circle is reported too, but a single outlying boundary pixel
can inflate it.

**A-CV-3: The boundary depends on the method.** A flame has no sharp edge. Each
segmentation method picks a different isophote:
* Otsu / fixed threshold: the chosen intensity level (Otsu falls near the
  midpoint between background and flame for a bimodal histogram).
* Background subtraction (MOG2): any pixel about 5σ above the background model,
  which is the faint outer edge. On synthetic data this gave a **+3.2 px**
  constant offset relative to the half-maximum isophote, with the growth rate
  unaffected (test `test_background_subtraction_after_ignition`).

So radii from different methods or thresholds are **not interchangeable**.
Compare experiments only with identical segmentation settings. Absolute radii
carry a method-dependent systematic offset, which is not in the reported
uncertainty (see A-UQ-3).

**A-CV-4: Intensity channel.** The default channel is `max(B,G,R)`. A soot-free
(blue) flame is dim in standard luma (0.114·B), and the max channel treats
blue, yellow and white emission the same way.

**A-CV-5: Candidate filtering.** A contour is a flame candidate only if its area
is ≥ `min_contour_area_px` and its mean intensity exceeds the surrounding 5 px
ring by at least `min_candidate_contrast` (default 0.06 ≈ 15 grey levels).
Without this floor, Otsu thresholds pure sensor noise once the flame is gone
(threshold ≈ 12 observed) and on-frame text overlays become "flames". A very
dim real flame below this floor will be reported as `not_detected`. Lower the
floor for such footage and check the result.

**A-CV-6: Tracking.** Constant-velocity prediction (in actual time) from the last
two accepted detections. A candidate outside the gates (by default 1 predicted
radius of centroid deviation, or 50 % radius change, with absolute floors of 10 px
and 5 px) is `rejected_discontinuity` and kept out of kinematics. After 10
consecutive misses the track resets. Fast real events such as ignition
transients or flame splitting may need wider gates.

**A-CV-7: No invented data.** A frame with no accepted detection has empty
measurements. Nothing is interpolated or carried forward. Derivatives use only
accepted samples and never span a gap longer than 3× the median frame interval.

**A-CV-8: Clipping.** If the flame touches the image border, its area and radius
are underestimated. The frame is flagged `touches_border` and the analysis gets a
`flame_clipped` issue.

**A-CV-9: Scores are heuristics.** `segmentation_quality` = (contour area ÷ total
foreground) × min(1, local contrast ÷ 0.25). `confidence` = quality × tracking
continuity. Neither is a calibrated probability of correctness.

**A-CV-10: Decoding.** FFmpeg is the default decoder. Interlaced frames are
deinterlaced with `yadif`, one output frame per input frame. Timestamps come from
the video stream's packet PTS, sorted into presentation order.

OpenCV is a fallback only. On the real ACME s-Flame downlink MP4 (interlaced
H.264), OpenCV returned *successfully decoded, all-black* frames. On a synthetic
reproduction, the same file decoded correctly or as black depending on unrelated
process state, so no per-file check can make it trustworthy. If every analysed
frame is exactly zero, the run gets an `all_frames_blank` **error**.

**A-CV-11: Static non-flame emitters.** Hot igniters, heated burner parts and
indicator LEDs are bright, compact and stable. The segmenter cannot tell them
from a flame. In the 19254H1 downlink video the engine reported 240 "detections"
of a static border glow while no flame was visible. Real-footage analysis
therefore needs a region of interest (planned) and visual confirmation. A
detection whose size and position never change is suspect.

## 3. Calibration

**A-CAL-1.** `mm_per_px = known_length_mm / measured_length_px`. This is valid only
for the camera, lens, zoom/focus, resolution and object distance at which the
reference was imaged. The engine **refuses** a calibration whose recorded image
size differs from the video's.

**A-CAL-2.** The reference must lie in the same plane as the flame, for example
the burner diameter for a burner-centred spherical flame. Perspective error from
an out-of-plane reference is not modelled.

**A-CAL-3.** Lens distortion is corrected only when the user supplies OpenCV
intrinsics (`DistortionCorrection`). Without it, distortion is an unmodelled
systematic error that grows towards the image edges.

## 4. Physics calculations

**A-PH-1: Equivalent spherical volume.** `V_eq = (4/3)·π·r³`. This is a model
estimate. It assumes a spherically symmetric flame and is meaningless for coflow
or jet flames (e.g. ACME CLD Flame and E-FIELD Flames). It is **never** a 3-D
measurement.

**A-PH-2: Kinematics.** `u_r = dr/dt` and `a_r = d²r/dt²` come from a
least-squares local polynomial (default: 7 points, order 2) fitted in *actual
timestamps*. This is the non-uniform generalisation of Savitzky–Golay.
Properties:
* It is exact for polynomials up to the fit order. The test checks this on
  irregular timestamps.
* It smooths. A feature shorter than about the window length (7 frames ≈ 0.23 s
  at 30 fps) is attenuated. Use a smaller window for fast transients, at the cost
  of more noise.
* At segment ends the window is shifted rather than shrunk, so the edge
  estimates are extrapolations and are less reliable.
* `numpy.gradient` finite differences are available as an unsmoothed reference.

**A-PH-3: Timestamps.** Per-frame presentation timestamps come from the
container: the video stream's packet PTS via `ffprobe` when decoding with FFmpeg
(the default), or OpenCV `CAP_PROP_POS_MSEC` with the OpenCV fallback. `index / fps` is used only if the container timestamps are
not strictly increasing, and the result records which source was used.
Variable frame rate is detected and reported.

**A-PH-4: Extinction time.** This is the time of *visible-emission* extinction
as seen by this camera and threshold. The estimate is the midpoint between the
last detected frame and the first missing frame, ± half that interval. It needs
≥ 5 consecutive missing frames at the end of the video. It is not a measurement
of chemical extinction, and a less sensitive camera will report an earlier time.

**A-PH-5: Plausibility limit.** |dr/dt| > 5 m/s produces a warning. That is far
above laminar flame speeds and above the mm/s to cm/s growth expected for
microgravity diffusion flames, so exceeding it almost always means a
segmentation or calibration error.

## 5. Uncertainty

**A-UQ-1: Components.** Uncertainty is split into a *random* part (independent
per frame, from boundary localisation) and a *systematic* part (correlated
across the video, from the calibration scale). They are combined in quadrature
only for display.

**A-UQ-2: Boundary model.** `σ_r = P·σ_edge / (2πr)` assumes the whole boundary
shifts coherently by `σ_edge` (default 1 px). On synthetic data the observed
residual scatter was far smaller than 1 px. The summary reports observed scatter
next to the assumed value (`radius_noise_check`) so this can be checked for each
video.

**A-UQ-3: Not included.** The reported uncertainty does not include:
* method or threshold boundary offset (A-CV-3)
* line-of-sight integration and optical thickness
* uncorrected lens distortion
* motion blur
* sensor saturation or blooming
* departure from sphericity
* perspective error

The reported uncertainty is therefore a **lower bound** on total error.

**A-UQ-4: First-order propagation.** `σ_V ≈ 4πr²σ_r` and `σ_A = 2πrσ_r`. A Monte
Carlo test confirms agreement within 3 % at 1 % relative radius uncertainty.
Accuracy degrades when relative uncertainty exceeds about 10 %.

**A-UQ-5: Derivative uncertainty.** Each derivative is a linear combination
`Σ wⱼ rⱼ`, so `σ = sqrt(Σ wⱼ² σⱼ²)` under independent errors. A Monte Carlo test
agrees within 8 %. The calibration contributes `|v|·σ_s/s` to the systematic part.

## 6. Data

**A-DATA-1.** NASA ACME data is available from PSI (CC0, verified 2026-10-30;
see `docs/DATA_AVAILABILITY_MATRIX.md`). Only individual files have been
inspected so far, and no model has been trained. No model may be described as
NASA-trained until the provenance records show it was.

**A-DATA-4.** ACME telemetry is stored as raw sensor voltages. Any conversion to
physical units (pressure, flow, temperature) needs the transfer functions from
NASA's engineering documents. Until those are verified, the values are reported
only as voltages.

**A-DATA-2.** All synthetic content carries the `SYNTHETIC_` filename prefix, an
on-frame watermark ("SYNTHETIC DEMO - NOT NASA DATA") and a ground-truth sidecar
with `data_class: "simulated"`. Its growth law is illustrative and has not been
fitted to any experiment.

**A-DATA-3.** Validation on synthetic video shows that the *measurement pipeline*
is correct. It does not show how well real flame images, which have soot
luminosity, burner glare, reflections and dim blue edges, can be segmented.
That requires real footage.

## 7. s-Flame test-point labels (NASA PSI-23)

**A-SF-1: Flame presence.** A flame is present when the OH* photomultiplier
(PMT1, 310 nm, 125 Hz) exceeds its pre-fuel baseline by
`max(10 × MAD, 0.02 V)` after a 0.1 s rolling median. It is *sustained* when
that lasts ≥ 1 s, with gaps ≤ 0.2 s bridged. PMT readings ≥ 4.2 V are excluded
because they occur before the script applies PMT gain. OH* was chosen because
every s-Flame fuel produces it and the hot-wire igniter does not emit
appreciably at 310 nm.

**A-SF-2: Outcome classes.**
* `extinguished` (event observed): emission ended ≥ 0.1 s before the fuel was
  shut off.
* `burning_at_fuel_off` (right-censored at the fuel shut-off).
* `ambiguous_nasa_extinction`: NASA's onboard detector declared extinction, but
  OH* persisted until the fuel stopped. NASA's detection criteria differ from
  ours, and the flame was probably weakening. These are excluded from timing
  labels rather than assigned.
* `no_sustained_flame`: e.g. ignition failure. 17 of these were logged by NASA
  as "EXTINCTION DETECTED" and must not count as flame lifetimes.

Agreement with NASA's own stop reasons: 184 of 220 "EXTINCTION DETECTED" are
`extinguished`, and all 23 "burner temperature limit" stops that had a flame
were still burning at fuel-off (see `sflame_quality_report.json`).

**A-SF-3: Lifetime origin.** `flame_duration_s` runs from emission onset, not
from commanded fuel-on. In 52 tests (mostly the helium round) emission began up
to 1.4 s before the logged fuel-on, apparently from fuel delivered before the
setpoint record (priming). The setpoint log is therefore not the time origin.

**A-SF-4: Composition and flow.** Flows are N2-equivalent indicated SLPM
(confirmed by the `...N2Slpm` parameter names in `as run` files). Gas conversion
factors for the real mixtures [DI §4.A.1] are not applied, so compositions and
flows are *nominal*. They are internally consistent for comparing tests with
the same bottles, but not absolute.

**A-SF-5: Oxygen.** Chamber O2 is known only at day level. On days with
"~30% and ~21%" (and some 17.5% tests on day 20190 per the final report), the
per-test O2 is not in the downloaded files, so `o2_nominal` is empty and those
tests must be excluded from, or modelled without, an O2 feature. Vitiation
lowers O2 through each test day (table footnote). `test_order_in_day` is
provided as a proxy and is not a measurement.

**A-SF-8: Re-runs under one test-point name.** NASA saves a re-run of a test
point as `<tp>_1`, `<tp>_2`, … (ACME-DOC-010 §8.1). Each run is its own row
(`test_point` = run ID; `test_point_base`, `run_suffix`). The single `_TP.txt`
of a test point is attributed only to the run whose data-header time matches
its "Script start" within 60 s. The single `as run` file is not attributed when
several runs share the name. This affects 19256B2/19256B2_1 and
20176K1/20176K1_1. A builder bug double-counted the first run and dropped the
second; it was fixed on 2026-10-30, and the model was retrained.

**A-SF-6: Source discrepancies resolved.** The experimental table's "N3–N6"
entries are corrected to N2 (rule SFLAME-T1, originals kept). For day 20190 the
table says 35% H2, but the final report and the MFC gas code say 45% H2. The
gas code is used.

**A-SF-7: Not causal.** Outcomes also depend on factors not in the table:
igniter timing and design (loop vs coil tip), burner heating, and chamber
vitiation. 19254H1 and 19254H3 had identical setpoints, yet one failed to
ignite and the other burned for 46 s. Any model built on this table predicts
associations within the s-Flame test matrix only.

## 8. Scientific image sequences and real-flame measurement

**A-IMG-1: Frame times.** Frame times come from the timestamp in each file name
(ms resolution). ACME camera frame intervals vary with exposure (DI §4.B), and
the variation is reported.

**A-IMG-2: Dark frame.** The dark frame is the per-pixel median of the first
`dark_frames` (default 10) frames, which must be flame-free. Whole-frame mean
brightness is checked and a warning is issued if the leading frames appear lit.
Per-pixel extremes are not used for this check because intensifier noise is
large.

**A-IMG-3: Hot pixels.** A 3×3 median filter removes radiation-induced hot
pixels (DI: "a star field"). It also slightly smooths real edges.

**A-IMG-4: Brightness scale.** One fixed 16→8-bit scale is used for the whole
sequence: the 99.95th percentile of dark-subtracted counts over sampled
*non-saturated* frames. Saturated frames (e.g. the ignition burst) are
excluded, because on 19304A7 they would have compressed the flame to ~5 % of
the range. Per-frame normalisation is never used.

**A-IMG-5: Saturation.** Frames whose raw maximum is ≥ 65,000 counts are
flagged. Their intensities and boundaries are not trustworthy.

**A-CAL-4: In-image burner calibration.** The s-Flame burner is a 6.35 mm
porous sphere (final report §3). Its silhouette is measured with
`measure_dark_disk`: radial half-depth edges in angular sectors, the
supply-tube sector excluded, and the centre refined by a circle fit. The
silhouette is soft because the flame emits in front of the sphere. That biases
the half-depth edge, so the stated uncertainty (sector scatter + 1 px) is a
lower bound. For 19304A7: 103 ± 2.5 px. For 19254C1: 98 ± 1 px, with the
centre within 4 px. The 5 % between-test difference exceeds both stated
uncertainties, so the method has a systematic error of about ±2.5 %, which is
added in quadrature to the per-test value. Per-test calibration is preferred.

**A-CV-12: Shell flames and the equivalent radius.** A spherical diffusion flame
is a thin luminous shell. In projection it is brightest at its limb, and its
brightness varies around the shell. On 19304A7 a single global (Otsu) threshold
captured only the brighter part of the shell, which **under-measures the
radius**. Later in the burn the flame opened into a C shape (local extinction /
flame hole) and then broke up. NASA's final report notes that s-Flame flames
were often not spherically symmetric at high flow, because of extra flow
through the sphere–tube joint. Consequences:
* `equivalent_volume_mm3` is suppressed when circularity < 0.75 or the flame
  is clipped (56 of 57 frames on 19304A7).
* The area-equivalent radius of a shell flame is reported, but it is *not* the
  flame-shell radius. A limb (outer-edge) circle fit is required for that and
  is not yet implemented.

**A-CV-13: Igniter contamination.** In the first ~0.5 s after ignition the hot
igniter tip and the ignition kernel dominate the image. Analyses should start
after this period. The OH* photomultiplier flame-on time (A-SF-1) gives the
time origin.

**A-CV-14: Shell-limb radius (`radius_method="limb"`).** The flame-shell radius
is the outer half-maximum edge of the luminous shell, fitted as a circle:
* polar profiles in 72 sectors, anchored on the *outermost* significant local
  maximum (so interior sources such as the igniter are ignored);
* RANSAC with inlier tolerance `max(2 px, 2 % R)`, then a least-squares refit;
* a sector must reach ≥ 20 % of the frame's brightest limb;
* a fit is accepted only with ≥ 8 inliers, ≥ 90° arc, ≥ 40 % coverage, RMS ≤
  `max(2 px, 3 % R)`, no saturation, and R ≥ `limb_min_radius_mm` (set to the
  burner radius 3.175 mm for s-Flame: the flame encloses its burner).

Validation on synthetic projected shells (full, C-shaped, half, clipped, with
a 5× brighter interior source): within 0.3 px of the true outer radius. On
PSI-23 19254C1 the area-equivalent radius under-measured the shell by a median
of 12 % (IQR 8.5–15.7 %, 75 frames). The limb fit measured 84 further frames in
which region segmentation had lost the dim shell. The 40 % coverage floor was
chosen on that same test: lower-coverage fits deviated from neighbouring frames
by up to 0.8 mm. It is therefore tuned on real data and should be re-checked on
other tests. The limb radius is the *outer* half-maximum edge, which lies within
about half the shell thickness plus the blur width inside the true outer
radius. It is not the location of peak heat release.

## 9. Flame-lifetime model (`backend/ml/sflame_model.py`)

**A-ML-1: Population and target.** Constant-flow s-Flame tests with a sustained
flame: 144 tests on 18 test days, of which 113 extinguished and 31 were still
burning at fuel shut-off (right-censored). Ramped tests are excluded because
their lifetime is set by the commanded ramp. Target: flame lifetime from OH*
emission onset to emission end (A-SF-1).

**A-ML-2: Features.** Only quantities fixed before ignition are allowed:
* nominal delivered fuel-line H2/CH4/C2H4 fractions,
* ln total flow,
* helium atmosphere,
* test order in the day (a vitiation proxy).

Post-ignition quantities are rejected by a guard, both in training and at
inference. O2 is excluded from the selected model because it is unknown on
mixed-O2 days. A model with O2 (105 tests) ranked better (C = 0.74), but it
cannot be applied to those days.

**A-ML-3: Model.** Log-normal accelerated-failure-time model, chosen against
Weibull and five feature sets by leave-one-test-day-out C-index. It assumes
censoring is non-informative given the features. That is questionable for the
29 tests stopped by the burner temperature limit, which may relate to flame
proximity.

**A-ML-4: What the validation says.** On held-out test days:
* C-index 0.70 (0.5 = no skill), so the model ranks conditions.
* Within a single day the ranking is weak (C ≈ 0.56).
* The median absolute log error on events is 0.73 (a factor of ~2.1), which is
  **not better** than the intercept-only baseline (0.65).

The model is therefore an interpretable description of how lifetime varies
across the test matrix. It is not an accurate predictor of absolute lifetime
for a new test day. Day-level effects (vitiation history, igniter design change
in round 2, unknown O2) dominate.

**A-ML-5: Intervals.** Predictive intervals integrate parameter uncertainty
(draws from the asymptotic normal) and are widened by a factor of 1.38 on σ.
That factor is the smallest that gives 80 % coverage of held-out-day events
(70 % before). The calibration uses the same predictions as model selection,
so it is mildly optimistic.

**A-ML-6: Associations, not causes.** Helium atmosphere: time ratio 0.52
(95 % CI 0.42–0.64). Test order: 0.76 per SD (0.65–0.89), consistent with
vitiation shortening later flames. Both effects are confounded with
round-level changes (igniter tip, bottles) and must not be read as causal.

**A-ML-7: Why no random forest / XGBoost.** With 144 censored observations in
18 groups, standard tree ensembles would either discard censoring (biasing
lifetimes low; demonstrated in `test_ignoring_censoring_biases_lifetimes_low`)
or need survival-specific implementations whose added flexibility the data
cannot support. They can be revisited with survival-capable implementations if
more test points (e.g. from PSI-10 or PSI-159) become usable.
