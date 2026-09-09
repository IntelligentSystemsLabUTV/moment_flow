#!/usr/bin/env python3
"""
MomentFlow ablation-study variant definitions for a single DSEC-Flow sequence.

Emits one self-contained ROS 2 parameter file per variant under
``logs/ablation/<sequence>/<variant>/config.yaml``. Each variant differs from
the reference configuration by exactly one knob (or one tightly coupled pair),
so that a delta in the benchmark metrics is attributable to that knob.

Alexandru Cretu <alexandru.cretu@uniroma2.it>

August 24, 2026
"""

# Copyright 2026 Alexandru Cretu
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import os
import re
from pathlib import Path

# Container-side workspace root. Parameter values are consumed inside the
# container, so they must never carry host paths.
# Override MOMENTFLOW_WS to generate parameter files for another workspace.
WS = os.environ.get('MOMENTFLOW_WS', '/home/neo/workspace')

# Reference configuration. Derived from config/moment_flow_dsec.yaml with three
# deliberate deviations, each recorded in the generated report:
#   - max_solve_events is 0: every event of the window reaches the solver.
#     The original campaign ran with a hardcoded 500 k cap, which is why its
#     runtime figures are not comparable with the ones measured here;
#   - iwe_enabled and debug are false, so the timing columns measure the
#     estimator rather than the diagnostic renderers;
#   - smooth_sweeps/beta exist in the current code and did not exist
#     during the campaign, so they are kept at the current default and ablated.
REFERENCE = {
    'autostart': True,
    'iwe_enabled': False,
    'publish_flow_hsv': True,
    'events_enabled': True,
    'debug': False,
    'max_window_ms': 100.0,
    'max_solve_events': 0,
    'num_threads': 0,
    'num_scales': 6,
    'cell_size_px': 4,
    'cell_min_mass': 3.0,
    'cell_min_lambda': 0.0005,
    'cell_max_residual_ratio': 0.95,
    'tile_min_mass': 5.0,
    'tile_min_cells': 2,
    'tile_min_lambda': 0.00001,
    'aperture_ratio': 0.04,
    'tikhonov_eps': 0.0005,
    'prior_lambda': 0.7,
    'reg_lambda': 5.0,
    'reg_sweeps': 12,
    'reg_sigma': 60.0,
    'smooth_sweeps': 4,
    'smooth_beta': 0.5,
    'refine_enabled': True,
    'refine_iters': 4,
    'track_enabled': True,
    'iwe_scale': 2,
    'max_speed_px_s': 3000.0,
    'save_enabled': True,
    'save_clear_output': True,
}

# Sequence sets. S1 is chosen to be cheap yet span the whole error range of the
# train split (EPE 1.64-7.07, AE 6.0-31.4 degrees in the 18-sequence campaign) so
# that an axis which helps easy scenes and hurts hard ones cannot hide. S2 adds
# two long, hard sequences to confirm contested axes. S3 is the full train split
# and is meant for the component-removal table and the final configuration only.
SEQUENCE_SETS = {
    'S1': [
        'thun_00_a',          # 41 frames,  EPE 2.51, easy, dense coherent motion
        'zurich_city_02_a',   # 64 frames,  EPE 7.07, hardest in the split
        'zurich_city_01_a',   # 97 frames,  EPE 3.56, mid
        'zurich_city_07_a',   # 100 frames, EPE 3.89, lowest AE in the split
        'zurich_city_11_a',   # 231 frames, EPE 1.64, easiest in the split
    ],
    'S2': [
        'thun_00_a', 'zurich_city_02_a', 'zurich_city_01_a', 'zurich_city_07_a',
        'zurich_city_11_a',
        'zurich_city_10_a',   # 752 frames, EPE 5.11
        'zurich_city_02_c',   # 795 frames, EPE 6.55, largest valid-pixel count
    ],
    'S3': [
        'thun_00_a', 'zurich_city_01_a', 'zurich_city_02_a', 'zurich_city_02_c',
        'zurich_city_02_d', 'zurich_city_02_e', 'zurich_city_03_a', 'zurich_city_05_a',
        'zurich_city_05_b', 'zurich_city_06_a', 'zurich_city_07_a', 'zurich_city_08_a',
        'zurich_city_09_a', 'zurich_city_10_a', 'zurich_city_10_b', 'zurich_city_11_a',
        'zurich_city_11_b', 'zurich_city_11_c',
    ],
    # S4 is the sensitivity-analysis set: five sequences, 203.5 Mpx (43% of the
    # split's valid-pixel mass), pooled reference EPE 2.864 against 2.727 on the
    # full split, AE 13.13 against 11.93. Chosen over S1 because every member is
    # at least 440 frames long: S1's longest sequence is 231 frames, which
    # understated the output diffusion by 3x and the in-solve coupling by 3.4x,
    # since both act on a field that accumulates over time. The five span the
    # error range end to end (EPE 1.68-5.98, AE 7.9-30.6) and include the two
    # distinct failure modes -- large-displacement (zurich_city_02_c) and
    # angular (zurich_city_03_a, worst AE in the split) -- plus the sequence
    # whose event gap exercises the gap-filling path (zurich_city_05_a) and the
    # single largest pixel contributor (zurich_city_11_b, 16.3%).
    'S4': [
        'zurich_city_11_b',   # 965 frames, EPE 1.68, easy, largest pixel share
        'zurich_city_05_a',   # 629 frames, EPE 2.07, event gap
        'zurich_city_03_a',   # 440 frames, EPE 3.49, AE 30.6, worst direction
        'zurich_city_10_a',   # 752 frames, EPE 3.82, non-uniform GT indices
        'zurich_city_02_c',   # 795 frames, EPE 5.98, hardest at this length
    ],
}

# (variant name, tier, axis label, one-line description, parameter overrides).
#
# Tiers:
#   removal  one component switched off, for the paper's ablation table
#   p1       multi-level sweeps that defend a claim or resolve an open question
#   p2       secondary gates, conditioning safeguards and timing-only axes
#   protocol export-cadence experiments, which are not ablations of the method
#
# "schedule" entries additionally swap the save schedule; see run_variant.sh.
VARIANTS = [
    ('reference', 'reference', 'reference', 'Reference configuration', {}),

    # --- Component removal -------------------------------------------------
    ('rm_smooth', 'removal', 'removal', 'No output diffusion', {
        'smooth_sweeps': 0, 'smooth_beta': 0.0}),
    ('rm_refine', 'removal', 'removal', 'No residual re-warp', {
        'refine_enabled': False, 'refine_iters': 0}),
    ('rm_cell_gate', 'removal', 'removal', 'No cell reliability gate', {
        'cell_max_residual_ratio': 1.0}),
    ('rm_prior', 'removal', 'removal', 'No prior pull', {'prior_lambda': 0.0}),
    ('rm_reg', 'removal', 'removal', 'No spatial regularizer', {
        'reg_lambda': 0.0, 'reg_sweeps': 0}),
    ('rm_aperture', 'removal', 'removal', 'No aperture fallback', {
        'aperture_ratio': 0.0}),
    ('rm_track', 'removal', 'removal', 'No temporal tracking', {
        'track_enabled': False}),

    # --- P1: residual re-warp, the CMax-surrogate claim ---------------------
    ('refine_i1', 'p1', 'refine', '1 re-warp pass', {'refine_iters': 1}),
    ('refine_i2', 'p1', 'refine', '2 re-warp passes', {'refine_iters': 2}),
    ('refine_i6', 'p1', 'refine', '6 re-warp passes', {'refine_iters': 6}),
    ('refine_i8', 'p1', 'refine', '8 re-warp passes', {'refine_iters': 8}),

    # --- P1: tile pyramid --------------------------------------------------
    ('scales_4', 'p1', 'scales', '4 scales (8x8 tiles)', {'num_scales': 4}),
    ('scales_5', 'p1', 'scales', '5 scales (16x16 tiles)', {'num_scales': 5}),
    ('scales_7', 'p1', 'scales', '7 scales (64x64 tiles)', {'num_scales': 7}),
    ('scales_8', 'p1', 'scales', '8 scales (128x128 tiles)', {'num_scales': 8}),

    # --- P1: moment representation -----------------------------------------
    ('cell_2px', 'p1', 'cell', '2 px cells', {'cell_size_px': 2}),
    ('cell_8px', 'p1', 'cell', '8 px cells', {'cell_size_px': 8}),
    ('cell_16px', 'p1', 'cell', '16 px cells', {'cell_size_px': 16}),
    ('residual_040', 'p1', 'cell_gate', 'Residual gate 0.40', {
        'cell_max_residual_ratio': 0.40}),
    ('residual_060', 'p1', 'cell_gate', 'Residual gate 0.60', {
        'cell_max_residual_ratio': 0.60}),
    ('residual_085', 'p1', 'cell_gate', 'Residual gate 0.85', {
        'cell_max_residual_ratio': 0.85}),

    # --- P1: aperture handling ---------------------------------------------
    ('aperture_002', 'p1', 'aperture', 'Aperture ratio 0.02', {'aperture_ratio': 0.02}),
    ('aperture_010', 'p1', 'aperture', 'Aperture ratio 0.10', {'aperture_ratio': 0.10}),
    ('aperture_025', 'p1', 'aperture', 'Aperture ratio 0.25', {'aperture_ratio': 0.25}),

    # --- P1: prior strength -------------------------------------------------
    ('prior_035', 'p1', 'prior', 'Prior 0.35', {'prior_lambda': 0.35}),
    ('prior_150', 'p1', 'prior', 'Prior 1.5', {'prior_lambda': 1.5}),
    ('prior_300', 'p1', 'prior', 'Prior 3.0', {'prior_lambda': 3.0}),

    # --- P1: spatial regularizer -------------------------------------------
    ('reg_weak', 'p1', 'regularizer', 'lambda 1, 6 sweeps', {
        'reg_lambda': 1.0, 'reg_sweeps': 6}),
    ('reg_strong', 'p1', 'regularizer', 'lambda 15, 16 sweeps', {
        'reg_lambda': 15.0, 'reg_sweeps': 16}),
    ('reg_sigma_20', 'p1', 'regularizer', 'Charbonnier sigma 20', {'reg_sigma': 20.0}),
    ('reg_sigma_iso', 'p1', 'regularizer', 'Isotropic coupling (sigma 1e9)', {
        'reg_sigma': 1000000000.0}),

    # --- P1: output diffusion ----------------------------------------------
    ('smooth_2', 'p1', 'smoothing', '2 diffusion sweeps', {'smooth_sweeps': 2}),
    ('smooth_8', 'p1', 'smoothing', '8 diffusion sweeps', {'smooth_sweeps': 8}),
    ('smooth_16', 'p1', 'smoothing', '16 diffusion sweeps', {'smooth_sweeps': 16}),

    # Interaction check: per-scale re-warping is gated on a residual threshold
    # that steady tracking keeps below the trigger, so its value should only
    # become visible once the tracked field is removed.


    # --- P1: real-time knobs. The evaluation window is fixed at 100 ms, so
    # max_window_ms is part of the protocol and is not swept here.

    # max_speed_px_s is not a visualization knob: besides the HSV scale it
    # drives cell rejection (vn <= max_speed), the equivalent slope gate
    # (g2 >= 1/max_speed^2), a solver-internal clamp and the post-Stage-C field
    # clamp. This axis measures what the estimator role is worth. 100000 is the
    # declared maximum and effectively removes the bound from the core, leaving
    # only the display scale. Measured peak true motion on these sequences is
    # 818 px/s.
    ('speed_500', 'p1', 'max_speed', 'Speed limit 500 px/s', {
        'max_speed_px_s': 500.0}),
    ('speed_1000', 'p1', 'max_speed', 'Speed limit 1000 px/s', {
        'max_speed_px_s': 1000.0}),
    ('speed_2000', 'p1', 'max_speed', 'Speed limit 2000 px/s', {
        'max_speed_px_s': 2000.0}),
    ('speed_4000', 'p1', 'max_speed', 'Speed limit 4000 px/s', {
        'max_speed_px_s': 4000.0}),
    ('speed_unbounded', 'p1', 'max_speed', 'Effectively no bound (100000 px/s)', {
        'max_speed_px_s': 100000.0}),

    # --- P2: secondary gates and safeguards --------------------------------
    ('cell_lambda_0', 'p2', 'cell_lambda', 'No cell eigenvalue gate', {
        'cell_min_lambda': 0.0}),
    ('cell_lambda_1e4', 'p2', 'cell_lambda', 'Cell eigenvalue gate 1e-4', {
        'cell_min_lambda': 0.0001}),
    ('cell_lambda_5e3', 'p2', 'cell_lambda', 'Cell eigenvalue gate 5e-3', {
        'cell_min_lambda': 0.005}),
    ('cell_mass_1', 'p2', 'cell_mass', 'Cell min mass 1', {'cell_min_mass': 1.0}),
    ('cell_mass_10', 'p2', 'cell_mass', 'Cell min mass 10', {'cell_min_mass': 10.0}),
    ('tile_cells_1', 'p2', 'tile_gate', 'Tile min cells 1', {'tile_min_cells': 1}),
    ('tile_cells_5', 'p2', 'tile_gate', 'Tile min cells 5', {'tile_min_cells': 5}),
    ('tile_cells_10', 'p2', 'tile_gate', 'Tile min cells 10', {'tile_min_cells': 10}),
    ('tile_mass_0', 'p2', 'tile_gate', 'Tile min mass 0', {'tile_min_mass': 0.0}),
    ('tile_mass_15', 'p2', 'tile_gate', 'Tile min mass 15', {'tile_min_mass': 15.0}),
    ('tikhonov_1e4', 'p2', 'tikhonov', 'Tikhonov 1e-4', {'tikhonov_eps': 0.0001}),
    ('tikhonov_5e3', 'p2', 'tikhonov', 'Tikhonov 5e-3', {'tikhonov_eps': 0.005}),
    ('smooth_beta_025', 'p2', 'smoothing', 'Diffusion beta 0.25', {'smooth_beta': 0.25}),
    ('smooth_beta_100', 'p2', 'smoothing', 'Diffusion beta 1.0', {'smooth_beta': 1.0}),
    ('threads_1', 'p2', 'threads', '1 thread', {'num_threads': 1}),
    ('threads_2', 'p2', 'threads', '2 threads', {'num_threads': 2}),
    ('threads_4', 'p2', 'threads', '4 threads', {'num_threads': 4}),
    ('threads_8', 'p2', 'threads', '8 threads', {'num_threads': 8}),

    # --- Diagnostics: isolate the mechanism behind the no-smoothing divergence
    # Without output diffusion the estimator diverges on zurich_city_11_a in a
    # contiguous 109-frame run that never recovers, so the question is which
    # feedback path sustains it. Each of these removes one candidate path while
    # keeping smoothing off.
    ('diag_smooth_t1', 'diag', 'diag', 'No diffusion, single thread', {
        'smooth_sweeps': 0, 'smooth_beta': 0.0, 'num_threads': 1}),
    ('diag_smooth_prior0', 'diag', 'diag', 'No diffusion, no prior pull', {
        'smooth_sweeps': 0, 'smooth_beta': 0.0, 'prior_lambda': 0.0}),
    ('diag_smooth_reg0', 'diag', 'diag', 'No diffusion, no regularizer', {
        'smooth_sweeps': 0, 'smooth_beta': 0.0,
        'reg_lambda': 0.0, 'reg_sweeps': 0}),
    ('diag_smooth_norefine', 'diag', 'diag', 'No diffusion, no residual re-warp', {
        'smooth_sweeps': 0, 'smooth_beta': 0.0,
        'refine_enabled': False, 'refine_iters': 0}),
    ('diag_smooth_regstrong', 'diag', 'diag', 'No diffusion, strong regularizer', {
        'smooth_sweeps': 0, 'smooth_beta': 0.0,
        'reg_lambda': 15.0, 'reg_sweeps': 16}),

    # Dose-response on the re-warp iteration count with diffusion off. If the
    # instability compounds through the compositional iteration, divergence must
    # grow with the number of passes.
    ('diag_smooth_r1', 'diag', 'diag_dose', 'No diffusion, 1 re-warp pass', {
        'smooth_sweeps': 0, 'smooth_beta': 0.0, 'refine_iters': 1}),
    ('diag_smooth_r2', 'diag', 'diag_dose', 'No diffusion, 2 re-warp passes', {
        'smooth_sweeps': 0, 'smooth_beta': 0.0, 'refine_iters': 2}),
    ('diag_smooth_r6', 'diag', 'diag_dose', 'No diffusion, 6 re-warp passes', {
        'smooth_sweeps': 0, 'smooth_beta': 0.0, 'refine_iters': 6}),

    # Speed clamp as a trust region. Ground-truth flow on these sequences peaks
    # at 81.8 px per 100 ms window (818 px/s), so the shipped 3000 px/s admits
    # 3.7x the fastest real motion and never binds. These values bracket the
    # observed maximum with 22% and 83% headroom.
    ('diag_smooth_clamp1000', 'diag', 'diag_clamp', 'No diffusion, clamp 1000 px/s', {
        'smooth_sweeps': 0, 'smooth_beta': 0.0, 'max_speed_px_s': 1000.0}),
    ('diag_smooth_clamp1500', 'diag', 'diag_clamp', 'No diffusion, clamp 1500 px/s', {
        'smooth_sweeps': 0, 'smooth_beta': 0.0, 'max_speed_px_s': 1500.0}),
    ('diag_clamp1000', 'diag', 'diag_clamp', 'Reference plus clamp 1000 px/s', {
        'max_speed_px_s': 1000.0}),

    # --- Baseline search at the final reference (no cap, no per-scale re-warp).
    # Candidates are the single-knob winners of the earlier capped sweep, plus a
    # re-sweep of the mass gates, which the cap removal left ~3x mis-calibrated
    # because the gates are compared against mass_scale = 1/stride.
    ('t_mass_c1', 'tune', 'tune_mass', 'cell_min_mass 1', {'cell_min_mass': 1.0}),
    ('t_mass_c6', 'tune', 'tune_mass', 'cell_min_mass 6', {'cell_min_mass': 6.0}),
    ('t_mass_c10', 'tune', 'tune_mass', 'cell_min_mass 10', {'cell_min_mass': 10.0}),
    ('t_mass_t0', 'tune', 'tune_mass', 'tile_min_mass 0', {'tile_min_mass': 0.0}),
    ('t_mass_t2', 'tune', 'tune_mass', 'tile_min_mass 2', {'tile_min_mass': 2.0}),
    ('t_mass_t10', 'tune', 'tune_mass', 'tile_min_mass 10', {'tile_min_mass': 10.0}),
    ('t_prior15', 'tune', 'tune_single', 'prior 1.5', {'prior_lambda': 1.5}),
    ('t_prior30', 'tune', 'tune_single', 'prior 3.0', {'prior_lambda': 3.0}),
    ('t_sigma20', 'tune', 'tune_single', 'reg_sigma 20', {'reg_sigma': 20.0}),
    ('t_regstrong', 'tune', 'tune_single', 'reg 15/16', {
        'reg_lambda': 15.0, 'reg_sweeps': 16}),
    ('t_aper002', 'tune', 'tune_single', 'aperture 0.02', {'aperture_ratio': 0.02}),
    ('t_smooth2', 'tune', 'tune_single', 'diffusion 2 sweeps', {'smooth_sweeps': 2}),
    ('t_refine6', 'tune', 'tune_single', 'refine 6 passes', {'refine_iters': 6}),
    ('t_speed2000', 'tune', 'tune_single', 'speed bound 2000', {'max_speed_px_s': 2000.0}),

    # zurich_city_05_a diverges at the frozen baseline (contiguous ~100-frame
    # runaway, median EPE fine). Which removed/loosened mechanism was holding it?
    ('d05_cap500k', 'tune', 'diag05', 'Restore 500k event cap', {
        'max_solve_events': 500000}),
    ('d05_smooth8', 'tune', 'diag05', 'More diffusion (8 sweeps)', {
        'smooth_sweeps': 8}),
    ('d05_refine2', 'tune', 'diag05', 'Fewer Stage C passes (2)', {
        'refine_iters': 2}),
    ('d05_notrack', 'tune', 'diag05', 'No temporal tracking', {
        'track_enabled': False}),

    ('d05_nogapfill', 'tune', 'diag05', 'No gap filling', {
        'save_gap_fill': False}),

    # Probe runs: identical to the reference, but written to their own directory so
    # the completed ablation table is never overwritten. Used to recompute angular
    # error restricted to pixels with non-negligible ground-truth motion.
    ('probe_ae', 'probe', 'probe', 'Reference copy for AE analysis', {}),

    # Warm-start check. Identical configuration to the reference; the difference
    # is the binary, which now solves the stream preceding the first scheduled
    # export instead of discarding it. Measured on the three training sequences
    # whose ground truth starts late enough for the effect to exist:
    # zurich_city_07_a (index 874, 43.7 s of pre-roll), zurich_city_01_a
    # (index 134, 6.7 s) and thun_00_a (index 2, 0.1 s) as the null control.
    ('probe_warm', 'probe', 'probe', 'Reference copy, pre-roll solved', {}),

    # Reference copy kept for figure generation: run with KEEP_PREDICTIONS=1 so
    # the exported PNGs survive, in its own directory so that re-running it
    # cannot perturb the per-sequence numbers reported in the paper.
    ('probe_fig', 'probe', 'probe', 'Reference copy, predictions kept', {}),

    # --- Sensitivity: the four axes that define the geometry and the iteration.
    # Run on S4 rather than the full split: a full-split pass costs 5.8 h, and S4
    # keeps 43% of the pixel mass while fixing what made the original
    # five-sequence subset unusable here -- every S4 member is long enough for
    # the accumulating effects (diffusion, tracked field) to express themselves.
    #
    # s_ref is a reference re-run in its own directory. Event delivery is
    # load-dependent, so a sensitivity delta measured against a reference from an
    # earlier session mixes the parameter effect with run-to-run noise; s_ref
    # bounds that noise from the same session and leaves the completed removal
    # table's reference rows untouched.
    ('s_ref', 'sens', 'sens_reference', 'Reference re-run (same-session control)', {}),
    ('s_scales_4', 'sens', 'sens_scales', '4 scales (8x8 tiles)', {'num_scales': 4}),
    ('s_scales_5', 'sens', 'sens_scales', '5 scales (16x16 tiles)', {'num_scales': 5}),
    ('s_scales_7', 'sens', 'sens_scales', '7 scales (64x64 tiles)', {'num_scales': 7}),
    ('s_scales_8', 'sens', 'sens_scales', '8 scales (128x128 tiles)', {'num_scales': 8}),
    ('s_cell_2', 'sens', 'sens_cell', '2 px cells', {'cell_size_px': 2}),
    ('s_cell_8', 'sens', 'sens_cell', '8 px cells', {'cell_size_px': 8}),
    ('s_cell_16', 'sens', 'sens_cell', '16 px cells', {'cell_size_px': 16}),
    ('s_refine_1', 'sens', 'sens_refine', '1 re-warp pass', {'refine_iters': 1}),
    ('s_refine_2', 'sens', 'sens_refine', '2 re-warp passes', {'refine_iters': 2}),
    ('s_refine_6', 'sens', 'sens_refine', '6 re-warp passes', {'refine_iters': 6}),
    ('s_refine_8', 'sens', 'sens_refine', '8 re-warp passes', {'refine_iters': 8}),
    ('s_smooth_2', 'sens', 'sens_smooth', '2 diffusion sweeps', {'smooth_sweeps': 2}),
    ('s_smooth_8', 'sens', 'sens_smooth', '8 diffusion sweeps', {'smooth_sweeps': 8}),
    ('s_smooth_16', 'sens', 'sens_smooth', '16 diffusion sweeps', {'smooth_sweeps': 16}),

    # --- Protocol: export cadence, not an ablation of the method ------------
    ('schedule_2hz', 'protocol', 'schedule', 'Every 5th interval (2 Hz test cadence)', {}),

]

SCHEDULE_SUBSAMPLE = {'schedule_2hz': 5}


def render_float(value: float) -> str:
    """Render a float so YAML types it as a float.

    Bare ``1e-05`` is not a YAML float: the mantissa needs a decimal point, or
    the value is loaded as a string and ROS 2 rejects the parameter.
    """
    text = f'{value:.12g}'
    if 'e' in text or 'E' in text:
        mantissa, exponent = text.replace('E', 'e').split('e')
        if '.' not in mantissa:
            mantissa += '.0'
        return f'{mantissa}e{exponent}'
    if '.' not in text:
        text += '.0'
    return text


def render_yaml(params: dict) -> str:
    """Render a flat parameter dict as a moment_flow ROS 2 parameter file."""
    lines = ['/moment_flow:', '  ros__parameters:']
    for key in sorted(params):
        value = params[key]
        if isinstance(value, bool):
            rendered = 'true' if value else 'false'
        elif isinstance(value, str):
            rendered = f'"{value}"'
        elif isinstance(value, float):
            rendered = render_float(value)
        else:
            rendered = repr(value)
        lines.append(f'    {key}: {rendered}')
    return '\n'.join(lines) + '\n'


def gt_index_scheme(repo_root: Path, seq: str) -> tuple[int, int]:
    """First ground-truth file index and index step for one sequence.

    The DSEC training timestamp files carry only (from_us, to_us), so the node
    names its exports from save_first_index in steps of save_index_step.
    Those must reproduce the real ground-truth filenames, and the first index is
    NOT 2 everywhere: it is 134 for zurich_city_01_a and 874 for zurich_city_07_a,
    because the flow ground truth starts partway into those sequences. Getting it
    wrong does not fail loudly, it just makes the name-matched benchmark score the
    overlapping subset, so the values look plausible and are wrong.
    """
    gt_dir = repo_root / 'logs' / 'dsec' / seq / 'optical_flow_forward'
    indices = sorted(
        int(m.group(1)) for p in gt_dir.glob('*.png')
        if (m := re.search(r'(\d+)\.png$', p.name)))
    if not indices:
        raise SystemExit(
            f'no ground-truth PNGs under {gt_dir}; cannot derive the index scheme '
            f'for {seq}')
    step = indices[1] - indices[0] if len(indices) > 1 else 2
    return indices[0], step


def selected_variants(tiers: list[str] | None, with_reference: bool = True):
    """Variants belonging to the requested tiers, reference always included.

    ``with_reference=False`` drops it. Needed when a sweep carries its own
    control run: the reference directory holds the rows of an already published
    table, and re-running it there would leave that table half-refreshed.
    """
    if not tiers:
        chosen = list(VARIANTS)
    else:
        wanted = set(tiers)
        chosen = [v for v in VARIANTS if v[1] in wanted or v[1] == 'reference']
    if not with_reference:
        chosen = [v for v in chosen if v[1] != 'reference']
    return chosen


def resolve_sequences(args) -> list[str]:
    if args.set:
        return SEQUENCE_SETS[args.set]
    return [args.sequence]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sequence', default='thun_00_a', help='Single sequence name.')
    parser.add_argument(
        '--set', choices=sorted(SEQUENCE_SETS),
        help='Generate for every sequence of a named set instead of one sequence.')
    parser.add_argument(
        '--tier', action='append',
        choices=['removal', 'p1', 'p2', 'protocol', 'diag', 'tune', 'probe', 'sens'],
        help='Restrict to a tier; repeatable. The reference is always included.')
    parser.add_argument(
        '--no-reference', action='store_true',
        help='Drop the reference variant, leaving its existing run directory alone.')
    parser.add_argument(
        '--repo-root', type=Path,
        default=Path(__file__).resolve().parents[2],
        help='Host-side workspace root, used only to place generated files.')
    parser.add_argument('--list', action='store_true', help='Print variant names and exit.')
    parser.add_argument(
        '--list-sequences', action='store_true', help='Print the resolved sequences and exit.')
    args = parser.parse_args()

    chosen = selected_variants(args.tier, with_reference=not args.no_reference)

    if args.list:
        for name, tier, axis, description, _ in chosen:
            print(f'{name}\t{tier}\t{axis}\t{description}')
        return 0
    if args.list_sequences:
        for seq in resolve_sequences(args):
            print(seq)
        return 0

    written = 0
    for seq in resolve_sequences(args):
        out_root = args.repo_root / 'logs' / 'ablation' / seq
        for name, tier, axis, description, overrides in chosen:
            params = dict(REFERENCE)
            params.update(overrides)
            run_dir = f'{WS}/logs/ablation/{seq}/{name}'
            params['save_output_dir'] = run_dir
            params['timing_log_path'] = f'{run_dir}/timing_ms.csv'
            # run_variant.sh always writes an explicit (from, to, index) schedule
            # next to the run: the raw two-column file would make the node infer
            # indices that do not match the ground-truth filenames.
            params['save_timestamp_file'] = f'{run_dir}/schedule.txt'
            first_index, index_step = gt_index_scheme(args.repo_root, seq)
            params['save_first_index'] = first_index
            params['save_index_step'] = index_step

            target = out_root / name
            target.mkdir(parents=True, exist_ok=True)
            (target / 'config.yaml').write_text(render_yaml(params), encoding='utf-8')
            (target / 'subsample.txt').write_text(
                f'{SCHEDULE_SUBSAMPLE.get(name, 1)}\n', encoding='utf-8')
            (target / 'variant.txt').write_text(
                f'{name}\t{tier}\t{axis}\t{description}\t'
                + ';'.join(f'{k}={v}' for k, v in sorted(overrides.items()))
                + '\n',
                encoding='utf-8')
            written += 1

    print(f'Wrote {written} variant configs '
          f'({len(chosen)} variants x {len(resolve_sequences(args))} sequences)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
