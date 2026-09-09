/**
 * Moment Flow node parameter declarations.
 *
 * Alexandru Cretu <alexandru.cretu@uniroma2.it>
 *
 * August 28, 2026
 */

/**
 * Copyright 2026 Alexandru Cretu
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include "moment_flow/event_detector.hpp"

namespace moment_flow
{

void EventDetector::init_parameters()
{
  // aperture_ratio
  pmanager_->declare_double(
    "aperture_ratio",
    0.05, 0.0, 1.0, 0.0,
    "Minimum tile tensor eigenvalue ratio required for full 2D flow.",
    "Must be in [0, 1].",
    false,
    &aperture_ratio_);

  // autostart
  pmanager_->declare_bool(
    "autostart",
    false,
    "Start detection right after node initialization.",
    "Cannot be changed.",
    true,
    &autostart_);

  // cell_max_residual_ratio
  pmanager_->declare_double(
    "cell_max_residual_ratio",
    0.6, 0.0, 1.0, 0.0,
    "Maximum unexplained time-variance ratio accepted for each cell plane fit.",
    "Cells above this ratio are rejected before tile aggregation.",
    false,
    &cell_max_residual_ratio_);

  // cell_min_lambda
  pmanager_->declare_double(
    "cell_min_lambda",
    0.001, 0.0, 1000000.0, 0.0,
    "Minimum dominant spatial covariance eigenvalue required for a cell plane fit.",
    "Must be non-negative.",
    false,
    &cell_min_lambda_);

  // cell_min_mass
  pmanager_->declare_double(
    "cell_min_mass",
    3.0, 0.0, 1000000.0, 0.0,
    "Minimum event mass required for a cell plane fit.",
    "Must be non-negative.",
    false,
    &cell_min_mass_);

  // cell_size_px
  pmanager_->declare_integer(
    "cell_size_px",
    16, 1, 256, 1,
    "Moment-grid cell size [px].",
    "Cannot be changed at runtime.",
    true,
    &cell_size_px_);

  // debug
  pmanager_->declare_bool(
    "debug",
    true,
    "Enable heavy debug-only work: dense/event flow visualization images, per-window profiling "
    "logs, and diagnostic-only metrics (e.g. FWL). The estimated flow (flow_dense, flow_tiles), "
    "lightweight flow_tile_debug image, and end-to-end timing CSV (timing_log_path) are always "
    "produced regardless of this flag.",
    "Disable for lean, benchmark-ready operation; does not change the estimated flow.",
    false,
    &debug_);

  // events_enabled
  pmanager_->declare_bool(
    "events_enabled",
    false,
    "Enable event-supported sparse flow output by splatting warped events into a support mask.",
    "Disable for lean dense/tile optical-flow runtime; enable for sparse benchmarking.",
    false,
    &events_enabled_);

  // iwe_enabled
  pmanager_->declare_bool(
    "iwe_enabled",
    true,
    "Enable Image of Warped Events focus rendering and publishing.",
    "Cannot be changed at runtime.",
    true,
    &iwe_enabled_);

  // iwe_scale
  pmanager_->declare_integer(
    "iwe_scale",
    1, 1, 8, 1,
    "Downscale factor for the rendered IWE image (1 = full resolution).",
    "Must be positive.",
    false,
    &iwe_scale_);

  // max_solve_events
  pmanager_->declare_integer(
    "max_solve_events",
    500000, 0, 100000000, 1,
    "Cap on the events fed to the moment solver: busier windows are uniformly strided down and the "
    "mass gates are rescaled accordingly. 0 disables the cap.",
    "Cannot be changed at runtime.",
    true,
    &max_solve_events_);

  // max_speed_px_s
  pmanager_->declare_double(
    "max_speed_px_s",
    4000.0, 1.0, 100000.0, 0.0,
    "Upper saturation speed for flow colour visualization [px/s].",
    "Must be positive.",
    false,
    &max_speed_px_s_);

  // max_window_ms
  pmanager_->declare_double(
    "max_window_ms",
    10.0, 0.1, 1000.0, 0.0,
    "Temporal span accumulated per flow estimate [ms].",
    "Must be positive.",
    false,
    &max_window_ms_);

  // num_scales
  pmanager_->declare_integer(
    "num_scales",
    5, 1, 8, 1,
    "Tile-pyramid scales; scale l uses 2^(l-1) tiles per side.",
    "Cannot be changed at runtime.",
    true,
    &num_scales_);

  // num_threads
  pmanager_->declare_integer(
    "num_threads",
    0, 0, 256, 1,
    "Threads used by the per-event stages (event selection and packing, moment accumulation, event "
    "warping, support mask). 0 = as many as the OpenMP runtime offers. Does not affect the "
    "estimated flow, only how the work is spread.",
    "Cannot be changed at runtime.",
    true,
    &num_threads_);

  // prior_lambda
  pmanager_->declare_double(
    "prior_lambda",
    0.05, 0.0, 1000.0, 0.0,
    "Relative fallback prior strength in each tile solve.",
    "Must be non-negative.",
    false,
    &prior_lambda_);

  // publish_flow_hsv
  pmanager_->declare_bool(
    "publish_flow_hsv",
    true,
    "Publish the HSV renderings of the estimated flow, which exist for visualization only. The "
    "numeric flow fields are always published; the heavier dense and event-supported renderings "
    "are additionally produced only when 'debug' is set.",
    "Cannot be changed at runtime.",
    true,
    &publish_flow_hsv_);

  // refine_enabled
  pmanager_->declare_bool(
    "refine_enabled",
    false,
    "Enable Stage C: compositional warped re-solve (CMax-style iterations) after the "
    "coarse-to-fine solve.",
    "Set to false to skip the refinement stage.",
    false,
    &refine_enabled_);

  // refine_iters
  pmanager_->declare_integer(
    "refine_iters",
    2, 0, 20, 1,
    "Maximum Stage C warped re-solve iterations; early-stops at sub-pixel residual.",
    "Must be non-negative; 0 disables the extra iterations.",
    false,
    &refine_iters_);

  // reg_lambda
  pmanager_->declare_double(
    "reg_lambda",
    0.0, 0.0, 1000000000.0, 0.0,
    "Spatially coupled tile-flow regularization strength.",
    "Set to 0, or set reg_sweeps to 0, for an exact no-op.",
    false,
    &reg_lambda_);

  // reg_sigma
  pmanager_->declare_double(
    "reg_sigma",
    1000000000.0, 1e-06, 1000000000000.0, 0.0,
    "Charbonnier edge threshold [px/s] for coupled regularization; very large is nearly isotropic.",
    "Must be positive.",
    false,
    &reg_sigma_);

  // reg_sweeps
  pmanager_->declare_integer(
    "reg_sweeps",
    0, 0, 16, 1,
    "Gauss-Seidel sweeps for coupled tile-flow regularization.",
    "Set to 0, or set reg_lambda to 0, for an exact no-op.",
    false,
    &reg_sweeps_);

  // save_clear_output
  pmanager_->declare_bool(
    "save_clear_output",
    true,
    "Delete stale PNG files from save_output_dir before saving a new benchmark run.",
    "Only .png files in the output directory are removed.",
    true,
    &save_clear_output_);

  // save_enabled
  pmanager_->declare_bool(
    "save_enabled",
    false,
    "Save raw dense optical-flow estimates as DSEC-compatible 16-bit PNG files.",
    "Enable for offline benchmarking; leave disabled for live visualization.",
    true,
    &save_enabled_);

  // save_first_index
  pmanager_->declare_integer(
    "save_first_index",
    2, 0, 9223372036854775807, 1,
    "First output file index when the timestamp file does not include explicit indices.",
    "DSEC training flow for thun_00_a uses 2,4,6,...",
    true,
    &save_first_index_);

  // save_gap_fill
  pmanager_->declare_bool(
    "save_gap_fill",
    true,
    "Keep solving ordinary windows over the stream skipped between non-adjacent scheduled export "
    "windows, discarding their output, so the tracked field stays as fresh as it is on a "
    "contiguous schedule.",
    "Only applies between two scheduled windows, and only when the skipped span exceeds half of "
    "max_window_ms. On the contiguous DSEC training schedule it never triggers.",
    true,
    &save_gap_fill_);

  // save_index_step
  pmanager_->declare_integer(
    "save_index_step",
    2, 1, 9223372036854775807, 1,
    "Output file-index increment when the timestamp file does not include explicit indices.",
    "DSEC training flow for thun_00_a uses a step of 2.",
    true,
    &save_index_step_);

  // save_output_dir
  pmanager_->declare_string(
    "save_output_dir",
    "/home/neo/workspace/logs/moment_flow",
    "Directory where DSEC-format raw optical-flow PNGs are written.",
    "Created automatically when save_enabled is true.",
    true,
    &save_output_dir_);

  // save_timestamp_file
  pmanager_->declare_string(
    "save_timestamp_file",
    "",
    "Optional DSEC forward-flow timestamp file; when set, saved estimates are aligned to these "
    "intervals.",
    "Rows must contain from_us,to_us and may optionally contain a file index.",
    true,
    &save_timestamp_file_);

  // smooth_beta
  pmanager_->declare_double(
    "smooth_beta",
    0.5, 0.0, 10.0, 0.0,
    "Neighbour weight of the post-refine confidence diffusion, relative to the tile's own "
    "confidence. 0 makes it a no-op.",
    "Cannot be changed at runtime.",
    true,
    &smooth_beta_);

  // smooth_sweeps
  pmanager_->declare_integer(
    "smooth_sweeps",
    4, 0, 32, 1,
    "Confidence-weighted diffusion sweeps applied to the composed tile field after the refine "
    "passes. 0 disables this post-smoothing.",
    "Cannot be changed at runtime.",
    true,
    &smooth_sweeps_);

  // tikhonov_eps
  pmanager_->declare_double(
    "tikhonov_eps",
    0.001, 1e-12, 1000.0, 0.0,
    "Tikhonov regularization added to cell/tile dynamic solve terms.",
    "Must be positive.",
    false,
    &tikhonov_eps_);

  // tile_min_cells
  pmanager_->declare_integer(
    "tile_min_cells",
    3, 0, 1000000, 1,
    "Minimum valid cells required before solving a tile.",
    "Must be non-negative.",
    false,
    &tile_min_cells_);

  // tile_min_lambda
  pmanager_->declare_double(
    "tile_min_lambda",
    1e-06, 0.0, 1000000000.0, 0.0,
    "Minimum tile geometry eigenvalue required before solving a tile.",
    "Must be non-negative.",
    false,
    &tile_min_lambda_);

  // tile_min_mass
  pmanager_->declare_double(
    "tile_min_mass",
    10.0, 0.0, 1000000000.0, 0.0,
    "Minimum summed cell confidence required before solving a tile.",
    "Must be non-negative.",
    false,
    &tile_min_mass_);

  // timing_log_path
  pmanager_->declare_string(
    "timing_log_path",
    "",
    "CSV file logging end-to-end MomentFlow timing and coarse per-stage timing for every processed "
    "window.",
    "Parent directory is created automatically. Empty disables the log. Always written when set, "
    "independent of 'debug'.",
    true,
    &timing_log_path_);
  // track_enabled
  pmanager_->declare_bool(
    "track_enabled",
    true,
    "Seed each window's coarse-to-fine solve with the tracked field of the previous window. "
    "Disabling it makes every window independent, which separates the temporal prior from the "
    "multiscale prior that prior_lambda also controls.",
    "Cannot be changed at runtime.",
    true,
    &track_enabled_);
}

}  // namespace moment_flow
