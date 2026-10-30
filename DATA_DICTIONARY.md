# Data Dictionary

## Quantity classes

See `SCIENTIFIC_ASSUMPTIONS.md` §1. Every column below carries one of the classes
`metadata`, `heuristic`, `image_derived` or `calculated`. Classes
`direct_measurement`, `predicted` and `simulated` are used by the data and ML
layers.

## Per-frame CV telemetry (`FrameMeasurement`)

Source of truth: `FIELD_DEFINITIONS` in `backend/vision/cv_engine.py`. The test
`test_data_dictionary_in_sync` fails if this table and the code diverge.

* `None`/empty means "not available". It never means zero.
* Fields ending `_mm` exist only when a calibration was supplied.
* `contour_px` (a simplified boundary polygon of ≤ 72 vertices in original-
  resolution pixels) is included in JSON output only.

| Field | Unit | Class | Definition |
|---|---|---|---|
| `experiment_id` | - | metadata | Experiment identifier supplied by the caller. |
| `frame_index` | - | metadata | Zero-based index of the decoded frame in the video. |
| `timestamp_s` | s | metadata | Presentation time relative to the first decoded frame. |
| `status` | - | metadata | detected / low_confidence / not_detected / rejected_discontinuity / frame_error. |
| `confidence` | 0-1 | heuristic | segmentation_quality x tracking continuity (not a probability). |
| `segmentation_quality` | 0-1 | heuristic | contour dominance x clipped local contrast (not a probability). |
| `contrast` | 0-1 | image_derived | (mean inside - mean of 5 px outer ring) / 255. |
| `n_candidates` | - | image_derived | Contours passing the minimum-area and local-contrast filters. |
| `threshold` | 0-255 | image_derived | Global threshold used (Otsu/fixed); empty for local/colour methods. |
| `centroid_x_px` | px | image_derived | Area centroid x of the filled flame region. |
| `centroid_y_px` | px | image_derived | Area centroid y of the filled flame region. |
| `bbox_x_px` | px | image_derived | Bounding box left. |
| `bbox_y_px` | px | image_derived | Bounding box top. |
| `bbox_w_px` | px | image_derived | Bounding box width. |
| `bbox_h_px` | px | image_derived | Bounding box height. |
| `enclosing_center_x_px` | px | image_derived | Minimum enclosing circle centre x. |
| `enclosing_center_y_px` | px | image_derived | Minimum enclosing circle centre y. |
| `enclosing_radius_px` | px | image_derived | Minimum enclosing circle radius. |
| `equivalent_radius_px` | px | image_derived | sqrt(area / pi); primary size measure. |
| `equivalent_radius_sigma_px` | px | calculated | 1-sigma random uncertainty of the equivalent radius. |
| `equivalent_diameter_px` | px | image_derived | 2 x equivalent radius. |
| `area_px2` | px^2 | image_derived | Projected flame area (pixel count of the filled contour). |
| `perimeter_px` | px | image_derived | Contour arc length. |
| `circularity` | - | image_derived | 4 pi A / P^2 (digitised circles score ~0.85-0.95). |
| `ellipse_major_px` | px | image_derived | Major axis length of the least-squares ellipse. |
| `ellipse_minor_px` | px | image_derived | Minor axis length of the least-squares ellipse. |
| `ellipse_angle_deg` | deg | image_derived | Ellipse orientation (OpenCV convention). |
| `eccentricity` | - | image_derived | sqrt(1 - (b/a)^2) of the fitted ellipse. |
| `boundary_roughness` | - | image_derived | std / mean of boundary distance from centroid. |
| `touches_border` | bool | image_derived | Flame region touches the image edge (size underestimated). |
| `radius_mm` | mm | calculated | Equivalent radius x calibration scale. |
| `radius_sigma_random_mm` | mm | calculated | Frame-independent (pixel) uncertainty of radius_mm. |
| `radius_sigma_scale_mm` | mm | calculated | Calibration (systematic, correlated) uncertainty of radius_mm. |
| `radius_sigma_mm` | mm | calculated | Random and scale uncertainty combined in quadrature. |
| `diameter_mm` | mm | calculated | 2 x radius_mm. |
| `area_mm2` | mm^2 | calculated | Projected area x scale^2. |
| `area_sigma_mm2` | mm^2 | calculated | 2 pi r sigma_r (total). |
| `perimeter_mm` | mm | calculated | Perimeter x scale. |
| `equivalent_volume_mm3` | mm^3 | calculated | (4/3) pi r^3 - equivalent SPHERICAL estimate, not a 3-D measurement. Empty when circularity < `min_circularity_for_volume` (0.75) or the flame is clipped. |
| `equivalent_volume_sigma_mm3` | mm^3 | calculated | 4 pi r^2 sigma_r (total, first order). |
| `radius_smoothed_px` | px | calculated | Local-polynomial smoothed equivalent radius. |
| `expansion_velocity_px_s` | px/s | calculated | dr/dt from timestamp-aware local polynomial fit. |
| `expansion_velocity_sigma_px_s` | px/s | calculated | 1-sigma random uncertainty of dr/dt. |
| `acceleration_px_s2` | px/s^2 | calculated | d2r/dt2 from the same fit. |
| `acceleration_sigma_px_s2` | px/s^2 | calculated | 1-sigma random uncertainty of d2r/dt2. |
| `expansion_velocity_mm_s` | mm/s | calculated | dr/dt in physical units. |
| `expansion_velocity_sigma_mm_s` | mm/s | calculated | Random + scale uncertainty in quadrature. |
| `acceleration_mm_s2` | mm/s^2 | calculated | d2r/dt2 in physical units. |
| `acceleration_sigma_mm_s2` | mm/s^2 | calculated | Random + scale uncertainty in quadrature. |
| `centroid_displacement_px` | px | calculated | Distance of centroid from the first accepted centroid. |
| `centroid_displacement_mm` | mm | calculated | centroid_displacement_px x scale. |
| `limb_radius_px` | px | image_derived | Shell-limb radius: RANSAC circle fit to outer half-maximum edges (radius_method=limb). |
| `limb_radius_sigma_px` | px | calculated | Bootstrap fit uncertainty and edge localisation (edge_sigma_px) in quadrature. |
| `limb_center_x_px` | px | image_derived | Fitted limb circle centre x. |
| `limb_center_y_px` | px | image_derived | Fitted limb circle centre y. |
| `limb_coverage` | 0-1 | image_derived | Fraction of angular sectors contributing a limb edge (partial shells < 1). |
| `limb_arc_deg` | deg | image_derived | Angular span of the limb edge points used in the fit. |
| `limb_rms_px` | px | image_derived | RMS distance of inlier edge points from the fitted circle. |
| `limb_fit_ok` | bool | calculated | Fit sufficient: >= 8 inliers, arc >= 90 deg, coverage >= 40 %, RMS <= max(2 px, 3 % R), not saturated. |
| `limb_radius_mm` | mm | calculated | limb_radius_px x calibration scale. |
| `limb_radius_sigma_mm` | mm | calculated | Random and calibration-scale uncertainty in quadrature. |
| `warnings` | - | metadata | Per-frame notes and warnings, '; '-separated in CSV. |

## Detection status values

| Status | Used in kinematics | Meaning |
|---|---|---|
| `detected` | yes | Accepted candidate, confidence ≥ `min_confidence` |
| `low_confidence` | yes (flagged) | Accepted candidate, confidence < `min_confidence` |
| `not_detected` | no | No candidate passed area/contrast filters |
| `rejected_discontinuity` | no | Candidate failed tracking gates; geometry kept for inspection |
| `frame_error` | no | Frame could not be decoded/retrieved |

## Analysis-level JSON (`schema: flame-in-freefall/cv-analysis/v1`)

| Key | Content |
|---|---|
| `engine_version` | CV engine version string |
| `video` | `VideoMetadata`: filename (no server path), container, codec, size, nominal fps, reported frame count, duration, file size |
| `timestamp_source` | `container_pts` or `nominal_fps` |
| `calibration` | Calibration record incl. `mm_per_px`, `mm_per_px_sigma`, camera fields; `null` if uncalibrated |
| `config` | Full `AnalysisConfig` (segmentation, tracking, derivatives); enough to reproduce the run |
| `summary` | Status counts, detection rate, radius/velocity statistics, peak radius, shape stability, extinction estimate, noise check, processing time and system info |
| `issues` | Validation issues `{code, severity, message, frame_index}` |
| `field_definitions` | The table above, machine-readable |
| `measurements` | Array of per-frame records |

## Synthetic ground-truth sidecar (`*.groundtruth.json`)

`data_class: "simulated"`. Contains the generator spec and, per frame:
`frame_index`, `timestamp_s`, `flame_visible`, `radius_px`, `radius_rate_px_s`,
`radius_accel_px_s2`, `center_x_px`, `center_y_px` (and `source_frame_index`
for variable-frame-rate files).

## s-Flame test-point table (`data/processed/sflame_test_points.csv`)

Built by `python -m backend.data.sflame_dataset` from NASA PSI-23 (CC0-1.0, DOI
10.60555/k57n-p030). `sflame_manifest.json` records the SHA-256 of every input
file. One row per test point (289 rows). Sources: `[IDD]` ACME-DOC-010 Rev D,
`[NIDD]` ACME non-imaging data file description, `[DI]` s-Flame Data
Interpretation (2021). Labelling rules: `SCIENTIFIC_ASSUMPTIONS.md` §7.

| Column | Unit | Class | Definition / source |
|---|---|---|---|
| `test_point` | – | metadata | NASA test-point ID `YYDDD<letter><n>` [DI §4.A.1] |
| `test_day`, `test_date_utc`, `test_order_in_day` | – | metadata | Day code, header date, order by fuel-on time within the day (vitiation proxy) |
| `round` | – | metadata | 1 = nitrogen-diluted (2019–Jan 2020), 2 = helium-diluted (May–Jul 2020) |
| `fuel_bottle_code`, `fuel_bottle` | –, JSON mole fractions | direct_measurement (setup) | MFCA3 gas code and composition [IDD Table 34] |
| `diluent_mfc_gas` | – | direct_measurement (setup) | MFCA2 gas (always N2 in s-Flame) |
| `flow_programme` | – | calculated | constant / ramp_up / ramp_down / up_down / stepped, from the commanded setpoints |
| `fuel_on_utc`, `fuel_off_utc`, `fuel_duration_s` | ISO time, s | direct_measurement | First non-zero fuel setpoint, next zero setpoint (ms resolution) |
| `atmosphere_day`, `atmosphere_inert` | – | direct_measurement (day level) | From the experimental table after correction SFLAME-T1 |
| `o2_nominal` | mole fraction | direct_measurement (day level, nominal) | Single nominal O2 for the day; **empty** when the day mixed O2 levels |
| `initial_fuel_slpm`, `initial_diluent_slpm`, `initial_total_slpm`, `max_total_slpm`, `min_total_slpm` | SLPM (N2-equivalent, indicated) | calculated | `V / 5 × full scale` [NIDD], **no gas conversion factor** |
| `initial_fuel_species_fraction`, `initial_x_{H2,CH4,C2H4,N2,He}` | mole fraction | calculated | Delivered fuel-line mixture from bottle composition and indicated flows (nominal) |
| `n_flow_steps` | – | calculated | Number of distinct commanded flow states |
| `planned_constant_flow_s`, `burner_temperature_limit_c` | s, °C | direct_measurement (plan) | From `as run<tp>.txt` (available for 237 tests). Planned time is the censoring horizon |
| `nasa_stop_reason`, `nasa_ignition_utc`, `nasa_extinction_detected_utc` | –, ISO time (1 s resolution) | direct_measurement | From `_TP.txt`. "EXTINCTION DETECTED" is the script's normal stop path |
| `flame_on_utc`, `flame_off_utc`, `flame_duration_s` | ISO time, s | calculated | Sustained OH* emission (PMT1, 125 Hz) per A-SF-1 |
| `ignition_delay_s` | s | calculated | `flame_on − fuel_on`. Negative values mean emission before the logged fuel-on (flagged) |
| `pmt1_baseline_v`, `pmt1_peak_v` | V | direct_measurement | Raw photomultiplier voltages; not radiometrically calibrated |
| `outcome`, `event_observed` | – | calculated | See A-SF-2. `event_observed` = True (extinction), False (censored), empty (not applicable) |
| `total_slpm_at_extinction`, `fuel_species_fraction_at_extinction`, `time_since_last_flow_change_s` | SLPM, mole fraction, s | calculated | Commanded state when emission ended (extinguished tests only) |
| `detection_lag_s` | s | calculated | `fuel_off − flame_off`: delay between emission loss and the automatic fuel shut-off |
| `pta3_kpa_at_ignition_low_confidence` | kPa | calculated | PTA3 `(V−0.5)·14.5038·10/4` psia [NIDD]. **Uncalibrated transducer** [DI] |
| `quality_flags` | – | metadata | `;`-separated flags (see `sflame_quality_report.json`) |

## Flame-lifetime model artifacts (`models/sflame_lifetime/`)

| File | Content |
|---|---|
| `model.json` | Schema `flame-in-freefall/sflame-lifetime-model/v1`: model version, population, target definition, training-data SHA-256, distribution, standardiser, coefficients, covariance, interval inflation, feature ranges, coefficient table (time ratios, 95 % CI, p), validation, limitations |
| `evaluation_metrics.json` | Leave-one-test-day-out metrics for all candidates and the baseline |
| `feature_schema.json` | Features (name, description, unit), training ranges, forbidden (post-ignition) inputs |
| `cv_predictions.csv` | Held-out-day 10/50/90 % lifetime quantiles for every training test point |

Predictions are returned with `quantity_class: "predicted"`, a median, an 80 %
interval (including parameter uncertainty and the cross-validated inflation),
out-of-range warnings and the model's limitations.
