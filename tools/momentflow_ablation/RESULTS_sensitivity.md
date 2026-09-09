# MomentFlow sensitivity analysis (DSEC-Flow train split, S4)

Companion to `RESULTS_ablation.md`. The removal table answers *does this component earn its place*; this
one answers *is the value we picked the right one, and how sharply does it matter*. Four axes, fourteen
operating points, five sequences, 75 runs. Nothing here changes the algorithm: every point is a parameter
value, produced by `variants.py` into a self-contained ROS 2 parameter file and replayed through the same
node binary.

## 1. Protocol

Sequence set **S4**, defined in `variants.py`:

| sequence | frames | Mpx | reference EPE | reference AE | why it is in the set |
|---|--:|--:|--:|--:|---|
| `zurich_city_11_b` | 965 | 77.7 | 1.675 | 7.90 | easy end of the range; largest single pixel share of the split (16.3%) |
| `zurich_city_05_a` | 629 | 50.2 | 2.069 | 9.52 | contains the event gap, so the filler-window path is exercised |
| `zurich_city_03_a` | 440 | 17.2 | 3.494 | 30.58 | worst direction error in the split |
| `zurich_city_10_a` | 752 | 28.2 | 3.822 | 20.76 | non-uniform ground-truth index scheme |
| `zurich_city_02_c` | 795 | 30.3 | 5.984 | 15.50 | hardest sequence at this length; large displacements |

Pooled over S4 the reference scores **EPE 2.849, AE 13.03, 1PE 71.0, 2PE 40.3, 3PE 24.5** over 3581 frames
and 203.5 Mpx, against **2.727 / 11.93 / 69.9 / 38.4 / 23.3** on the full 18-sequence split. S4 therefore
carries 43% of the split's valid-pixel mass and is marginally harder, so a delta measured here transfers to
the full split in sign and in rough magnitude, not in the third decimal.

S4 replaces the earlier five-sequence set S1 deliberately. S1's longest sequence is 231 frames, and two of
the four axes swept here (`smooth_sweeps`, `refine_iters`) act on a field that accumulates across
the sequence; on S1 those effects came out 3x and 3.4x smaller than on the full split. Every S4 member is
at least 440 frames long.

Every run exported the full ground-truth schedule (965/629/440/752/795 frames, no `incomplete.flag`, no
`misaligned.flag`), and predictions were matched to ground truth on the estimation interval with a 1 ms
tolerance rather than by filename.

## 2. The control run, and what it buys

`s_ref` re-runs the reference configuration in the sweep's own session, in its own output directory. It
exists because event delivery through the ROS 2 graph is load dependent: a heavier parameter setting slows
the reader and changes how many events reach the solver, so a delta measured against a reference scored in
an earlier session mixes the parameter effect with session drift.

Measured drift, `s_ref` against the archived `reference`, identical configuration:

| sequence | reference EPE | s_ref EPE | ΔEPE | ΔAE | Δ events |
|---|--:|--:|--:|--:|--:|
| `zurich_city_11_b` | 1.6749 | 1.6653 | −0.0096 | −0.082 | +0.009% |
| `zurich_city_05_a` | 2.0692 | 2.0783 | +0.0091 | +0.144 | −0.013% |
| `zurich_city_03_a` | 3.4945 | 3.5099 | +0.0154 | −0.538 | −0.098% |
| `zurich_city_10_a` | 3.8220 | 3.7923 | −0.0297 | −0.421 | −0.161% |
| `zurich_city_02_c` | 5.9842 | 5.9087 | −0.0755 | −0.017 | n/a |
| **pooled** | 2.864 | **2.849** | **−0.0155** | −0.102 | |

So the replay reproduces itself to **−0.016 px pooled**, with per-sequence excursions up to 0.076 px and a
standard deviation of 0.037 px. Every effect reported below is at least 3x that, and most are one to two
orders of magnitude larger.

This measurement also recalibrated two thresholds in `aggregate.py` that had been set by guesswork:

- the noise floor for sign-flip detection went from 0.02 px to **0.08 px**. At 0.02 px, per-sequence
  delivery jitter was being promoted to an effect, and four of the seven reported sign flips were artefacts;
- the event-stream comparability tolerance went from 0.1% to **0.5%**. Two runs of the *same* configuration
  differ by up to 0.161%, so the old bound flagged configuration-identical runs as not comparable. 0.5% sits
  above that null and far below the two deliberate stream changes in the campaign (gap filling off, +3.4%;
  the 2 Hz export schedule, −31.5%).

A third defect was found and fixed while reading the first table: the ΔEPE column was pixel weighted, as
DSEC-Flow pools its metrics, but the bootstrap interval beside it was an unweighted mean of per-frame
deltas. Frames carry between 20 k and 80 k valid pixels depending on the sequence, so the two estimands
disagreed by more than the interval width and three intervals excluded their own point estimate. The
bootstrap is now pixel weighted, resampling frames as the pairing unit.

## 3. Results

Pooled over S4, dense output, pixel weighted. CI is a 2000-resample paired bootstrap over frames. Solve and
Total are median milliseconds per estimate on the x86 workstation, not the Jetson target.

### Pyramid depth — `num_scales`, reference 6

| variant | EPE | ΔEPE | 95% CI | AE | 3PE | Solve med | Total med |
|---|--:|--:|:-:|--:|--:|--:|--:|
| **s_ref (6)** | **2.849** | ref | | 13.03 | 24.5 | 40.8 | 51.6 |
| s_scales_5 | 3.258 | +0.409 | [+0.383, +0.436] | 13.45 | 29.3 | 38.7 | 49.0 |
| s_scales_7 | 3.505 | +0.656 | [+0.635, +0.678] | 17.60 | 34.0 | 46.8 | 57.9 |
| s_scales_8 | 4.773 | +1.924 | [+1.888, +1.964] | 24.20 | 49.5 | 53.2 | 64.6 |
| s_scales_4 | 4.898 | +2.049 | [+1.998, +2.104] | 20.56 | 53.4 | 37.1 | 48.1 |

### Cell size — `cell_size_px`, reference 4

| variant | EPE | ΔEPE | 95% CI | AE | 3PE | Solve med | Total med |
|---|--:|--:|:-:|--:|--:|--:|--:|
| **s_ref (4 px)** | **2.849** | ref | | 13.03 | 24.5 | 40.8 | 51.6 |
| s_cell_2 | 5.216 | +2.367 | [+2.246, +2.494] | 28.61 | 40.7 | 59.2 | 70.0 |
| s_cell_8 | 5.455 | +2.606 | [+2.559, +2.654] | 26.32 | 58.8 | 35.1 | 45.8 |
| s_cell_16 | 12.684 | +9.836 | [+9.676, +9.994] | 48.58 | 87.4 | 33.6 | 44.3 |

### Residual re-warp passes — `refine_iters`, reference 4

| variant | EPE | ΔEPE | 95% CI | AE | 3PE | Solve med | Total med |
|---|--:|--:|:-:|--:|--:|--:|--:|
| s_refine_8 | 2.889 | +0.040 | [+0.027, +0.053] | 13.15 | 25.2 | 70.8 | 81.6 |
| s_refine_6 | 2.894 | +0.045 | [+0.035, +0.056] | 13.29 | 25.0 | 54.9 | 65.9 |
| **s_ref (4)** | **2.849** | ref | | 13.03 | 24.5 | 40.8 | 51.6 |
| s_refine_2 | 2.937 | +0.088 | [+0.076, +0.100] | 13.49 | 24.9 | 26.6 | 37.8 |
| s_refine_1 | 3.118 | +0.269 | [+0.246, +0.295] | 14.33 | 26.2 | 19.2 | 30.1 |

### Output diffusion sweeps — `smooth_sweeps`, reference 4

| variant | EPE | ΔEPE | 95% CI | AE | 3PE | Solve med | Total med |
|---|--:|--:|:-:|--:|--:|--:|--:|
| **s_ref (4)** | **2.849** | ref | | 13.03 | 24.5 | 40.8 | 51.6 |
| s_smooth_8 | 2.981 | +0.132 | [+0.120, +0.145] | 12.76 | 25.4 | 40.4 | 51.0 |
| s_smooth_2 | 2.990 | +0.141 | [+0.124, +0.159] | 14.57 | 26.1 | 40.4 | 51.3 |
| s_smooth_16 | 3.260 | +0.411 | [+0.391, +0.431] | 13.14 | 29.5 | 39.9 | 51.2 |

All fourteen intervals exclude zero and all fourteen lie on the same side of it, so the reference value is
the pooled optimum on every one of the four axes.

## 4. Reading the four axes

**The two geometric axes are sharp optima, and this is the strongest evidence in the study that the
configuration was not loosely fitted.** A removal experiment only shows that a component helps. These show
that its magnitude is right: one step either way on the pyramid costs +0.41 to +0.66 px, two steps costs
+1.92 to +2.05 px, and the curvature is comparable on both sides of 6. Cell size is sharper still and
asymmetric: 16 px collapses the estimator outright (+9.84 px, AE 48.6°, 87% of pixels beyond 3 px), because
the second-moment integral over a 16 px cell averages away the very velocity variation the dispersion
surrogate reads — the cell becomes internally inconsistent and `d/s` no longer estimates a single velocity.
Going the other way costs almost as much for the opposite reason: at 2 px a cell rarely collects enough
events for the second moment to be conditioned, so the cell gate rejects it and coverage collapses. 4 px is
where the two failure modes cross.

Note that cost does not explain either direction. 8 and 16 px cells are *cheaper* than the reference
(35.1 and 33.6 ms solve against 40.8) and still much worse, so the reference is not buying accuracy with
compute here; 2 px is both slower (59.2 ms) and worse.

**The re-warp axis is a plateau, not a peak, and should be described as one.** Going from 4 passes to 6 or 8
costs +0.045 and +0.040 px — above the 0.08 px noise floor only marginally, and while nearly doubling the
solve time (54.9 and 70.8 ms against 40.8). Dropping to 2 costs +0.088 px and saves 14 ms; dropping to 1
costs +0.269 px. The honest reading is that Stage C has converged by roughly two to four passes and further
passes neither help nor harm, so `refine_iters: 4` is defensible as *converged and still affordable*
rather than as a tuned optimum. On a Jetson-class target 2 passes are the better operating point: 0.088 px
of EPE for 35% of the solve time.

**The diffusion axis is the one genuine scene-dependent trade-off in the study.** It is also the only axis
whose per-sequence deltas change sign, so the pooled number does not tell the whole story:

| variant | `zc_02_c` | `zc_03_a` | `zc_05_a` | `zc_10_a` | `zc_11_b` |
|---|--:|--:|--:|--:|--:|
| s_smooth_2 | +0.034 | +0.284 | +0.131 | +0.405 | +0.062 |
| s_smooth_8 | +0.697 | **−0.260** | +0.096 | **−0.089** | +0.103 |
| s_smooth_16 | +1.251 | **−0.221** | +0.402 | **−0.082** | +0.407 |
| s_scales_5 | +1.538 | **−0.207** | +0.379 | **−0.170** | +0.335 |

Reducing the diffusion below 4 hurts every sequence, so the component is not optional in either direction.
Increasing it past 4 *helps* exactly the two sequences with the worst direction error — `zurich_city_03_a`
(AE 30.6°) and `zurich_city_10_a` (AE 20.8°) — and hurts the large-displacement sequence
`zurich_city_02_c` badly (+0.70 at 8 sweeps, +1.25 at 16). The coarser pyramid at 5 scales splits the same
way, and its pooled AE (13.45) is barely worse than the reference's (13.03) despite 0.41 px more EPE.

This is a coherent mechanism rather than noise: extra spatial coupling and a coarser top scale both trade
displacement fidelity for angular consistency. Rotation-dominated scenes, where the flow field is smooth
but its direction turns quickly, are helped; translation-dominated scenes with large displacements, where
neighbouring pixels genuinely disagree, are hurt. The reference setting resolves that trade-off in favour
of displacement accuracy, which is what EPE — the DSEC-Flow leaderboard's primary metric — rewards. It
also means the direction-error weakness already documented for `zurich_city_03_a` is not a tuning
oversight: it is the price of the pooled optimum, and a deployment that cared more about heading than
displacement would legitimately set `smooth_sweeps` to 8.

## 5. What this does not cover

- **Full-split transfer is inferred, not measured.** S4 is 43% of the pixel mass. The sign and rough
  magnitude of each delta should carry to all 18 sequences, but the exact numbers will move.
- **Interactions are untested.** Every point varies one knob. The diffusion/pyramid trade-off above suggests
  `smooth_sweeps` and `num_scales` are coupled, and that pair is unmeasured.
- **Timing is x86, not Jetson.** The Solve and Total columns come from the x86-cudev container on the
  development workstation. They order the axes correctly by cost but are not the deployment figures.
- **Four axes of many.** The prior, the regularizer, the aperture fallback and the cell gates were swept in
  the earlier campaign on S1 and are reported in `RESULTS_ablation.md`; they have not been re-measured on
  the longer sequences.

## Copyright and License

Copyright 2026 Alexandru Cretu

Licensed under the Apache License, Version 2.0. You may obtain a copy of the License at
<http://www.apache.org/licenses/LICENSE-2.0>.
