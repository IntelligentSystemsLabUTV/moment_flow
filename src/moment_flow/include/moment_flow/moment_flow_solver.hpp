/**
 * Public API of the moment-based optical-flow estimator.
 *
 * dotX Automation s.r.l. <info@dotxautomation.com>
 *
 * August 28, 2026
 */

/**
 * Copyright 2024 dotX Automation s.r.l.
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

#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <vector>

#include <Eigen/Core>

namespace moment_flow::flow
{

/// Events for one window: pixel coordinates and time relative to t_ref_us [s].
struct Events
{
  std::vector<float> x;
  std::vector<float> y;
  std::vector<float> t;
  int64_t t_ref_us = 0;

  size_t size() const { return x.size(); }
};

struct MomentFlowParams
{
  int num_scales = 1;
  int cell_size_px = 16;
  float cell_min_mass = 3.0f;
  float cell_min_lambda = 1e-3f;
  float cell_max_residual_ratio = 0.6f;
  float tile_min_mass = 10.0f;
  int tile_min_cells = 3;
  float tile_min_lambda = 1e-6f;
  float aperture_ratio = 0.05f;
  float tikhonov_eps = 1e-3f;
  float prior_lambda = 0.05f;
  float flow_reg_lambda = 0.0f;
  int flow_reg_sweeps = 0;
  float flow_reg_sigma = 1e9f;
  float max_speed_px_s = 4000.0f;
};

bool operator==(const MomentFlowParams & a, const MomentFlowParams & b);

struct MomentFlowProfile
{
  int events_ingested = 0;
  int active_cells = 0;
  int valid_cells = 0;
  int residual_reject_cells = 0;
  int speed_reject_cells = 0;
  int full_rank_tiles = 0;
  int aperture_tiles = 0;
  int fallback_tiles = 0;
  int prior_tiles = 0;
  int final_full_rank_tiles = 0;
  int final_aperture_tiles = 0;
  int final_fallback_tiles = 0;
  int reg_total_tiles = 0;
  int reg_modified_tiles = 0;
  int reg_warped_geometry_tiles = 0;
  double reg_mean_delta_speed = 0.0;
  double ingest_ms = 0.0;
  double stage_a_ms = 0.0;
  double stage_b_ms = 0.0;
  double smooth_ms = 0.0;
  double total_solve_ms = 0.0;
};

class MomentFlow
{
public:
  MomentFlow(int img_w, int img_h, MomentFlowParams params);
  ~MomentFlow();

  MomentFlow(const MomentFlow &) = delete;
  MomentFlow & operator=(const MomentFlow &) = delete;
  MomentFlow(MomentFlow &&) noexcept;
  MomentFlow & operator=(MomentFlow &&) noexcept;

  bool compatible(int img_w, int img_h, const MomentFlowParams & params) const;
  int num_vars() const;
  const MomentFlowProfile & profile() const;

  void set_prior_scale(float scale);
  void set_mass_scale(float scale);
  void set_max_threads(int threads);

  void reset();
  void ingest(const Events & events);
  void solve(const Eigen::VectorXf & warm_start, Eigen::VectorXf & output);
  void solve_coarse_to_fine(
    const Events & events,
    const Eigen::VectorXf & warm_start,
    Eigen::VectorXf & output);
  void final_tile_confidence(std::vector<float> & confidence) const;

private:
  class Impl;
  std::unique_ptr<Impl> impl_;
};

}  // namespace moment_flow::flow
