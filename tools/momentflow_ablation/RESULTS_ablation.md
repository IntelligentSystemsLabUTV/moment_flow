# MomentFlow ablation study — DSEC-Flow train split

Component-removal ablation of the MomentFlow estimator over the complete DSEC-Flow **train** split: 8 configurations x 18 sequences = 144 runs, all complete, none flagged as incomplete or misaligned. 8170 forward-flow intervals, 476.5 Mpx of ground-truth-valid pixels.

Every row was measured in a single session against one shared reference, so the paired per-frame deltas are not affected by the session-to-session variation documented in Section 6.

## 1. Setup

| Item | Value |
| --- | --- |
| Split | DSEC-Flow train, all 18 sequences with public forward-flow ground truth |
| Baseline | `tools/momentflow_ablation/BASELINE_moment_flow_dsec.yaml` |
| Estimation window | 100 ms, matching the ground-truth interval |
| Event selection | every event of the window; no decimation |
| Matching | prediction paired with the ground-truth interval it was solved over (1 ms tolerance) |
| Host | Intel Core Ultra 9 275HX, 24 cores, DUA `x86-cudev` container |
| Cost | 33 min per full 18-sequence pass; 4.4 h for the table |

## 2. Baseline accuracy

Dense field, scored on the DSEC valid mask.

| Sequence | Frames | Mpx | EPE | AE | 1PE | 2PE | 3PE |
| --- | --: | --: | --: | --: | --: | --: | --: |
| `thun_00_a` | 41 | 2.62 | 2.21 | 9.36 | 65.30 | 30.49 | 17.30 |
| `zurich_city_01_a` | 97 | 6.55 | 3.34 | 13.41 | 74.19 | 41.71 | 25.66 |
| `zurich_city_02_a` | 64 | 4.19 | 5.74 | 25.85 | 90.60 | 70.13 | 51.52 |
| `zurich_city_02_c` | 795 | 30.28 | 5.98 | 15.50 | 86.72 | 63.86 | 46.37 |
| `zurich_city_02_d` | 362 | 13.26 | 4.34 | 9.28 | 79.03 | 48.60 | 32.78 |
| `zurich_city_02_e` | 470 | 18.41 | 4.93 | 16.57 | 88.17 | 65.80 | 46.51 |
| `zurich_city_03_a` | 440 | 17.21 | 3.49 | 30.58 | 88.07 | 62.85 | 40.34 |
| `zurich_city_05_a` | 629 | 50.20 | 2.07 | 9.52 | 65.93 | 31.19 | 16.54 |
| `zurich_city_05_b` | 393 | 27.72 | 3.25 | 6.61 | 72.76 | 43.21 | 28.82 |
| `zurich_city_06_a` | 642 | 48.50 | 1.87 | 8.93 | 63.09 | 27.78 | 13.76 |
| `zurich_city_07_a` | 100 | 6.77 | 3.42 | 5.45 | 71.20 | 40.58 | 26.25 |
| `zurich_city_08_a` | 349 | 29.13 | 1.88 | 7.62 | 61.13 | 28.47 | 15.40 |
| `zurich_city_09_a` | 638 | 20.98 | 3.08 | 21.38 | 85.32 | 56.16 | 33.98 |
| `zurich_city_10_a` | 752 | 28.15 | 3.82 | 20.76 | 86.86 | 61.01 | 40.41 |
| `zurich_city_10_b` | 383 | 14.48 | 3.50 | 25.34 | 87.21 | 60.21 | 38.20 |
| `zurich_city_11_a` | 231 | 18.90 | 1.56 | 8.86 | 54.97 | 20.32 | 9.35 |
| `zurich_city_11_b` | 965 | 77.66 | 1.67 | 7.90 | 59.00 | 24.77 | 11.90 |
| `zurich_city_11_c` | 819 | 61.49 | 1.83 | 8.23 | 59.95 | 26.38 | 13.94 |
| **Sequence mean** | **8170** | **476.51** | **3.22** | **13.82** | **74.42** | **44.59** | **28.10** |
| **Pixel-weighted** | | | **2.72** | **11.86** | **69.89** | **38.68** | **23.19** |

Per-sequence values are given to two decimals: repeating the identical configuration produces a mean drift of +0.007 px with a maximum of 0.120 px, so the third decimal is not reproducible. Aggregates are stable to about 0.01 px because the scatter is symmetric and averages out.

## 3. Component removal

Pixel-weighted endpoint error over all 8170 intervals. The confidence interval is a paired per-frame bootstrap; "beyond noise" counts sequences whose delta exceeds the 0.12 px reproducibility bound.

| Component removed | Seq-mean | Pixel-w EPE | Delta | 95% CI | AE | 3PE | Worsened | Beyond noise |
| --- | --: | --: | --: | :-: | --: | --: | --: | --: |
| *(none: full method)* | 3.223 | **2.727** | — | ref | 11.93 | 23.30 | | |
| Output diffusion | 19.549 | 26.173 | **+23.445** | [+21.84, +22.57] | 45.67 | 68.80 | 18/18 | 18/18 |
| Temporal tracking | 7.956 | 7.378 | **+4.651** | [+4.78, +4.99] | 25.21 | 51.88 | 18/18 | 18/18 |
| Residual re-warp | 4.615 | 3.813 | **+1.085** | [+1.23, +1.35] | 15.95 | 31.61 | 18/18 | 18/18 |
| In-solve coupling | 3.535 | 2.976 | +0.248 | [+0.30, +0.32] | 12.90 | 25.99 | 18/18 | 15/18 |
| Prior | 3.375 | 2.814 | +0.087 | [+0.10, +0.13] | 12.38 | 23.09 | 15/18 | 8/18 |
| Cell reliability gate | 3.338 | 2.800 | +0.073 | [+0.09, +0.11] | 12.05 | 23.50 | 14/18 | 8/18 |
| Aperture handling | 3.232 | 2.727 | **-0.000** | [-0.01, +0.00] | 12.02 | 23.42 | 10/18 | 0/18 |

### Per-sequence deltas

| Sequence | Frames | Output diffusion | Temporal tracking | Residual re-warp | In-solve coupling | Prior | Cell reliability gate | Aperture handling |
| --- | --: | --: | --: | --: | --: | --: | --: | --: |
| `thun_00_a` | 41 | +1.70 | +2.77 | +1.42 | +0.11 | +0.34 | +0.22 | +0.04 |
| `zurich_city_01_a` | 97 | +2.07 | +3.63 | +1.20 | +0.32 | +0.04 | -0.03 | +0.10 |
| `zurich_city_02_a` | 64 | +5.51 | +7.17 | +4.61 | +0.63 | +0.96 | +0.21 | +0.11 |
| `zurich_city_02_c` | 795 | +31.20 | +5.08 | +1.49 | +0.44 | +0.14 | +0.14 | -0.05 |
| `zurich_city_02_d` | 362 | +14.32 | +6.61 | +1.58 | +0.78 | +0.06 | +0.16 | -0.06 |
| `zurich_city_02_e` | 470 | +13.36 | +5.15 | +1.13 | +0.60 | +0.20 | +0.39 | -0.02 |
| `zurich_city_03_a` | 440 | +19.13 | +3.22 | +1.56 | +0.48 | -0.03 | +0.07 | -0.03 |
| `zurich_city_05_a` | 629 | +42.11 | +5.22 | +0.43 | +0.12 | +0.10 | +0.02 | -0.03 |
| `zurich_city_05_b` | 393 | +22.28 | +6.71 | +0.80 | +0.20 | +0.05 | +0.22 | +0.01 |
| `zurich_city_06_a` | 642 | +20.99 | +4.41 | +0.63 | +0.13 | +0.01 | -0.03 | +0.01 |
| `zurich_city_07_a` | 100 | +3.28 | +7.65 | +1.91 | +0.20 | +0.25 | +0.33 | -0.03 |
| `zurich_city_08_a` | 349 | +7.07 | +4.30 | +1.17 | +0.17 | +0.17 | +0.07 | +0.01 |
| `zurich_city_09_a` | 638 | +12.73 | +3.30 | +0.68 | +0.34 | -0.10 | +0.07 | +0.01 |
| `zurich_city_10_a` | 752 | +16.36 | +5.54 | +3.11 | +0.42 | +0.45 | +0.21 | +0.09 |
| `zurich_city_10_b` | 383 | +6.94 | +4.06 | +1.23 | +0.32 | -0.07 | -0.04 | -0.01 |
| `zurich_city_11_a` | 231 | +12.93 | +1.84 | +0.42 | +0.05 | +0.14 | +0.01 | +0.02 |
| `zurich_city_11_b` | 965 | +34.97 | +5.03 | +1.25 | +0.18 | +0.02 | -0.02 | -0.01 |
| `zurich_city_11_c` | 819 | +26.91 | +3.49 | +0.44 | +0.12 | +0.01 | +0.05 | +0.00 |

## 4. Three tiers, and three different failure mechanisms

**Essential.** Output diffusion, temporal tracking and the residual re-warp each degrade every one of the 18 sequences, by between 1 and 23 px. Removing any of them does not degrade the method, it breaks it. What makes this more than a ranking is that the three fail in distinguishable ways.

*Output diffusion* fails as a function of elapsed time. Short sequences lose 64-96%: `thun_00_a` (41 frames) +1.70 px, `zurich_city_02_a` (64) +5.51, `zurich_city_07_a` (100) +3.28. Long sequences lose one to two orders of magnitude: `zurich_city_05_a` (629) +42.11, `zurich_city_11_b` (965) +34.97, and `zurich_city_11_b` is the *easiest* long sequence at a baseline of 1.67 px. That is the signature of a compounding divergence being suppressed, not of a smoothness prior improving local accuracy. Angular error rises from 11.93 to 45.67 degrees, i.e. direction becomes close to uninformative.

*Residual re-warp* fails as a function of motion magnitude, not time. Its worst cases are the two fastest sequences, `zurich_city_02_a` +4.61 and `zurich_city_10_a` +3.11, while the 965-frame `zurich_city_11_b` loses +1.25 and the 470-frame `zurich_city_02_e` only +1.13. This is what the truncation-bias argument of Section 2.6 predicts: the single-pass tile regression underestimates displacements that cross cells within the window, an error that grows with speed and not with sequence length.

*Temporal tracking* fails on both axes, which is expected of a state that is both accumulated over time and relied on more heavily when displacement is large.

**Real but modest.** In-solve coupling (+0.248), prior (+0.087) and the cell reliability gate (+0.073). The coupling deserves emphasis out of proportion to its magnitude: it is the only small effect that worsens 18 of 18 sequences, with 15 beyond the noise bound. Perfect directional consistency at a small magnitude is stronger evidence than a larger but inconsistent effect, and it is the strongest available defence of the regularizer parameters.

**Null.** Aperture handling produces a pooled delta of -0.000 px, with 10 sequences worse, 8 better and none beyond the noise bound. The largest single deviation, 0.113 px, is smaller than the 0.120 px reproducibility bound of the reference configuration itself.

## 5. The aperture result

This is a measured null across two independent designs. The removal row above spans 18 sequences and 8170 intervals. A separate five-level sweep on a five-sequence subset placed `aperture_ratio` values of 0, 0.02, 0.04, 0.10 and 0.25 within 0.04 px of one another, with no monotone trend.

The probable mechanism is that the aperture test is rarely reached. `cell_min_lambda` and `cell_max_residual_ratio` reject ill-conditioned cells before tile aggregation, so few tiles arrive at the eigenvalue-ratio test with a genuinely degenerate information matrix.

The mechanism is principled and may well matter on data dominated by long isolated edges; DSEC driving footage does not appear to supply enough of them. The recommendation is to describe Equation (aperture test) as an implementation safeguard rather than as a contribution, and to report the null. A measured null on one mechanism is a stronger position than an unsupported claim, and it raises the credibility of the components that do survive.

## 6. Reproducibility

Repeating the reference configuration on all 18 sequences produced a mean drift of +0.007 px and a maximum of 0.120 px. Six sequences reproduced exactly. The cause is load-dependent event delivery in the replay path: the reader-side QoS is `KEEP_LAST`, so a consumer that falls behind loses events, and the loss depends on machine load. Measured directly, replaying at twice real time changes the number of events reaching the solver by 0.23%.

Three consequences are reflected in this report. Per-sequence values are quoted to two decimals. Deltas below roughly 0.2 px are reported together with their per-sequence consistency rather than on the strength of the confidence interval alone. And every row of the table was measured in one session against a single reference, because a reference measured separately is not comparable: an earlier attempt that re-ran the reference in isolation invalidated 36 of 55 runs, which the event-stream integrity check detected.

## 7. Guards

Each run is rejected rather than reported if it fails any of three checks: the number of exported predictions must equal the schedule length (`incomplete.flag`), every export must find a ground-truth interval within 1 ms (`misaligned.flag`), and a variant that changes neither the event budget nor the window length must process the same event stream as the reference to within 0.1%. All 144 runs of this table passed all three.

## 8. Reproducing

```bash
python3 tools/momentflow_ablation/variants.py --set S3 --tier removal
PURGE_PREDICTIONS=1 dua exec --timeout 40000s -- \
  bash tools/momentflow_ablation/run_all.sh S3 removal
python3 tools/momentflow_ablation/aggregate.py --set S3
```

144 runs, 4.4 h on 24 cores. A `flock` prevents a second concurrent sweep, which would corrupt results because every variant clears its output directory. `PURGE_PREDICTIONS=1` deletes the prediction PNGs after scoring; a full pass writes about 8 GiB of them.

## Copyright and License

Copyright 2026 Alexandru Cretu

Licensed under the Apache License, Version 2.0. You may obtain a copy of the License at <http://www.apache.org/licenses/LICENSE-2.0>.
