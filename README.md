# MomentFlow

Event-based dense optical flow that replaces iterative contrast maximization with an incremental spatio-temporal moment surrogate for event alignment.

MomentFlow summarizes each window of events with local first- and second-order moments on a fixed cell grid, extracts one normal-flow constraint per cell in closed form, and fuses those constraints over a coarse-to-fine tile pyramid. It is **training-free**: there is no learned component and no dataset-specific weight. The estimator is stateful across windows and runs on embedded hardware on CPU alone, with no CUDA or GPU acceleration; its latency is workload dependent, so see [Runtime](#runtime) before assuming a processing budget.

This repository accompanies the paper below and contains the reference C++/ROS 2 implementation, the parameter file of the reported configuration, and the evaluation, ablation and submission tooling used to produce its tables.

## Paper

> **MomentFlow: Event-Based Optical Flow Using Incremental Spatio-Temporal Moments as an Event-Alignment Surrogate**
> Alexandru Cretu, Jaleh Farmani, Alessandro Tenaglia, Roberto Masocco, Simone Mattogno, Daniele Carnevale
> Submitted to *MDPI Sensors*.

Correspondence: `alexandru.cretu@uniroma2.it`

## Results

On the **official DSEC-Flow test split**, evaluated by the benchmark server:

| EPE (px) | AE (deg) | 1PE (%) | 2PE (%) | 3PE (%) |
| --- | --- | --- | --- | --- |
| **2.878** | **9.787** | 68.731 | 40.123 | 25.238 |

On the 18-sequence **training split** with the same configuration: EPE 2.696 px, AE 11.925 degrees.

Relative to MultiCM, the full contrast-maximization reference, MomentFlow improves every reported aggregate metric and improves EPE on every one of the seven test sequences: 2.878 px against 3.472 px EPE, and 9.787 against 13.983 degrees AE.

Among the `optim`-class leaderboard entries closest to this operating point it places second by EPE, ahead of MultiCM (3.472 px) and RTEF (4.881 px) and behind ERTFlow (2.086 px, an anonymous entry marked "under review"). The paper compares a deliberately restricted set of optimization-based and CMax-related methods rather than the complete leaderboard.

### Runtime

Profiled on an NVIDIA Jetson AGX Orin Developer Kit (L4T 36.4.4, ROS 2 Jazzy, 50 W power mode, `jetson_clocks` disabled), CPU/OpenMP only, over the same five-sequence subset used for the parameter sensitivity. End-to-end time measures computation after the event window has been formed, and excludes the 100 ms of event support the window spans.

| Configuration | EPE [px] | Median [ms] | P95 [ms] | Within 100 ms | Throughput [Mev/s] |
| --- | --- | --- | --- | --- | --- |
| `refine_iters: 4` (reported) | 2.849 | 167.92 | 272.05 | 7.1% | 9.54 |
| `refine_iters: 1` (reduced) | 3.118 | 78.01 | 129.46 | 71.5% | 20.13 |

The residual-refinement budget dominates: its median cost falls from 119.76 ms to 30.17 ms between the two, while the initial sweep (28.4 ms) and the support and event masks (13.3 ms) are effectively unchanged. Trading 0.269 px of EPE for `refine_iters: 1` therefore roughly halves median and P95 latency.

**On this profile the reported configuration does not meet a 100 ms budget**, and the reduced-refinement configuration meets it on 71.5% of windows. Embedded suitability is workload dependent rather than guaranteed; the five-sequence subset is deliberately event-dense. See the paper for the stage distributions.

## Repository layout

```
src/
├── moment_flow/                     ROS 2 package: the estimator and its node
│   ├── include/moment_flow/
│   │   ├── moment_flow_solver.hpp        solver API (pimpl)
│   │   ├── event_detector.hpp            node class
│   │   ├── event_store.hpp               internal event representation
│   │   └── parameter_manager.hpp         parameter declaration with descriptors
│   ├── src/moment_flow/
│   │   ├── moment_flow_solver.cpp        the estimator: moments, tile fusion, coupling
│   │   ├── optical_flow.cpp              window solve, re-warping, diffusion, rendering
│   │   ├── workers.cpp                   windowing and the benchmark export schedule
│   │   └── ...                           node scaffolding, one concern per file
│   ├── config/
│   │   ├── moment_flow_dsec.yaml         the reported DSEC configuration
│   │   └── moment_flow.yaml              live-camera configuration
│   └── launch/moment_flow.launch.py
└── dsec_publisher/                  ROS 2 node replaying DSEC HDF5 as event packets

tools/
├── download_dsec_sequence.sh        fetch one DSEC training sequence
├── download_dsec_test_sequence.sh   fetch one DSEC test sequence
├── dsec_flow_benchmark/             the DSEC flow scorer (EPE, AE, 1PE/2PE/3PE)
├── momentflow_ablation/             component ablation and parameter sensitivity
└── dsec_test_submission/            build and package a benchmark submission
```

## Dependencies

ROS 2 **Jazzy** on Linux. Everything else is either standard ROS 2 or available from `packages.ros.org`:

```bash
rosdep install --from-paths src -y --ignore-src
```

`moment_flow` depends only on `rclcpp`, `rcl_interfaces`, `sensor_msgs`, `std_msgs`, `std_srvs`, `rclcpp_components`, Eigen 3.4, OpenCV, OpenMP, and the two upstream event-camera packages `event_camera_msgs` and `event_camera_codecs`.

`dsec_publisher` additionally needs `rclpy`, `tf2_ros`, `h5py`, NumPy and PyYAML. DSEC event files are Blosc-compressed HDF5, which needs the corresponding HDF5 filter plugin at runtime:

```bash
pip install hdf5plugin
export HDF5_PLUGIN_PATH=$(python3 -c "import hdf5plugin, os; print(os.path.join(os.path.dirname(hdf5plugin.__file__), 'plugins'))")
```

Without it, opening a DSEC sequence fails with `OSError: Can't read data (filter returned failure)` or a missing-plugin-directory error. The plugin is not expressible as a rosdep key, so it is not declared in `package.xml`.

`event_camera_codecs` changed the return type of `EventProcessor::eventExtTrigger` between releases. CMake probes the header that is actually installed and adapts, so both the current and older APIs build without intervention.

## Build

```bash
source /opt/ros/jazzy/setup.sh
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=RelWithDebInfo
source install/setup.sh
```

## Run

```bash
ros2 launch moment_flow moment_flow.launch.py \
  config:=$(ros2 pkg prefix moment_flow)/share/moment_flow/config/moment_flow.yaml
```

The node is also a composable component, `moment_flow::EventDetector`, and ships a standalone executable, `moment_flow_app`.

### Interface

| Direction | Name | Type | Contents |
| --- | --- | --- | --- |
| in | `/event_packet` | `event_camera_msgs/EventPacket` | encoded event stream; remap to your driver |
| out | `~/flow_dense` | `sensor_msgs/Image`, `32FC2` | dense image velocity [px/s] |
| out | `~/flow_tiles` | `sensor_msgs/Image`, `32FC2` | velocity on the native tile grid [px/s] |
| out | `~/flow_events` | `sensor_msgs/Image`, `32FC2` | dense flow masked to event-supported pixels |
| out | `~/flow_dense_debug`, `~/flow_tile_debug`, `~/flow_events_debug` | `sensor_msgs/Image`, `BGR8` | HSV flow visualizations, only when `publish_flow_hsv` is set |
| out | `~/iwe_image` | `sensor_msgs/Image`, `MONO8` | Image of Warped Events, alignment diagnostic |
| service | `~/enable` | `std_srvs/SetBool` | start or stop processing at runtime |

Velocities follow the physical convention: positive is the direction the scene point moves in the image. Set `autostart: true` to begin on startup, or leave it false and call `~/enable`.

The numeric fields `~/flow_dense` and `~/flow_tiles` are the node's output and are always published. `publish_flow_hsv` adds the three BGR8 HSV renderings, which exist only for visualization; `events_enabled` adds the event-supported pair; `iwe_enabled` adds the IWE diagnostic. The dense and event-supported HSV renderings are also only computed when `debug` is set, so with `debug: false` only `~/flow_tile_debug` carries an image.

### Parameters

All parameters are declared with full descriptors, so `ros2 param describe /moment_flow <name>` reports the meaning, the admissible range and whether the value is fixed after startup. `config/moment_flow_dsec.yaml` is the authoritative record of the reported configuration; the principal algorithmic values are:

| Parameter | Symbol in the paper | Value |
| --- | --- | --- |
| `max_window_ms` | window duration | 100.0 ms |
| `num_scales` | pyramid levels | 6, so a 32x32 final tile grid |
| `cell_size_px` | cell size | 4 px |
| `aperture_ratio` | aperture threshold | 0.04 |
| `prior_lambda` | prior strength | 0.70, halved per pyramid pass |
| `reg_lambda`, `reg_sweeps`, `reg_sigma` | in-solve coupling | 5.0, 12, 60.0 px/s |
| `smooth_sweeps`, `smooth_beta` | final diffusion | 4, 0.5 |
| `refine_iters` | residual re-warp passes | 4 |
| `max_speed_px_s` | speed clamp | 3000 px/s |

Two knobs matter for cost rather than accuracy: `num_threads` spreads the per-event stages over OpenMP threads, and `max_solve_events` caps the events fed to the solver by uniform striding, rescaling the mass gates accordingly. The reported configuration leaves the cap disabled.

Setting `save_enabled` writes the estimates as DSEC-format 16-bit PNG files, optionally aligned to a ground-truth timestamp schedule, which is how the benchmark submissions were produced.

## Reproducing the paper

Everything needed to reproduce the reported tables is in this repository. All of it drives the same loop: replay a DSEC sequence through `dsec_publisher`, run MomentFlow with `save_enabled`, and score the exported PNGs against the ground truth.

The tooling defaults to the workspace paths used for the published runs. Point it at your own checkout with

```bash
export MOMENTFLOW_WS=/path/to/this/workspace
```

### 1. Get the data

```bash
tools/momentflow_ablation/download_train_split.sh      # the 18 training sequences
tools/download_dsec_test_sequence.sh interlaken_00_b   # one test sequence
```

Sequences land under `logs/dsec/<sequence>/`, the layout the run scripts expect. Set `DSEC_ROOT` to put them elsewhere.

### 2. Score a single run

`tools/dsec_flow_benchmark/` is the scorer: EPE, AE and 1PE/2PE/3PE under the DSEC global valid-pixel aggregation, with ground-truth matching by name, order or timestamp.

```bash
python3 -m tools.dsec_flow_benchmark \
  --gt-dir   logs/dsec/thun_00_a/optical_flow_forward \
  --pred-dir logs/moment_flow/thun_00_a/dense \
  --pred-units px_per_second --output-json result.json
python3 -m tools.dsec_flow_benchmark.self_test   # unit tests for the metrics and IO
```

### 3. Component ablation and parameter sensitivity

| File | Purpose |
| --- | --- |
| `variants.py` | the reported configuration, every ablation and sensitivity variant, and the sequence sets, each with the reason it was chosen |
| `run_variant.sh` | replay one sequence under one variant and score it |
| `run_all.sh` | drive the whole campaign |
| `aggregate.py` | pool per-sequence results, paired per-frame bootstrap intervals |
| `BASELINE_moment_flow_dsec.yaml` | frozen copy of the reported configuration used by the campaign |
| `RESULTS_ablation.md`, `RESULTS_sensitivity.md` | the measured tables behind the paper |

`run_all.sh` takes a sequence set (`S1`--`S4`) or a single sequence name, followed by the tiers to sweep. `aggregate.py` then pools whatever has been scored:

```bash
# component ablation over the full 18-sequence training split
tools/momentflow_ablation/run_all.sh S3 removal
python3 tools/momentflow_ablation/aggregate.py --set S3

# parameter sensitivity over the five-sequence subset, against its own control run
NO_REFERENCE=1 tools/momentflow_ablation/run_all.sh S4 sens
python3 tools/momentflow_ablation/aggregate.py --set S4 --baseline s_ref
```

Every delta is measured against `--baseline`, and the sensitivity sweep names its own same-session control (`s_ref`) rather than a reference scored earlier: event delivery is load-dependent, so comparing across sessions folds run-to-run noise into the parameter effect.

The sensitivity subset is deliberately harder than the full split: pooled EPE 2.849 px against 2.73 px for the ablation baseline. `variants.py` records why each of its five sequences was chosen.

### 4. Test-set submission

`tools/dsec_test_submission/` produces a submission archive: `make_configs.py` imports the reported configuration from `variants.py` so the submitted settings cannot drift from the ablation baseline, `run_test_sequence.sh` replays one sequence against the official timestamp schedule, and `package_submission.py` verifies the result — seven directories, the expected file counts, six-digit names, and the 16-bit three-channel PNG header — before zipping it.

### One thing to know before re-running

The estimator carries state across windows, so a sequence is not a set of independent frames: results depend on the recency of the tracked field. Replay each sequence from its beginning.

## Citation

```bibtex
@article{cretu2026momentflow,
  title   = {MomentFlow: Event-Based Optical Flow Using Incremental Spatio-Temporal
             Moments as an Event-Alignment Surrogate},
  author  = {Cretu, Alexandru and Farmani, Jaleh and Tenaglia, Alessandro and
             Masocco, Roberto and Mattogno, Simone and Carnevale, Daniele},
  journal = {Sensors},
  year    = {2026},
  note    = {Submitted}
}
```

## Copyright and License

Copyright 2026 Alexandru Cretu

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License.

You may obtain a copy of the License at <http://www.apache.org/licenses/LICENSE-2.0>.

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

See the License for the specific language governing permissions and limitations under the License.
