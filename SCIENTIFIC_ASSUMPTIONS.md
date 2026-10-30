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
