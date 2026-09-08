/**
 * Moment Flow node definition.
 *
 * Alexandru Cretu <alexandru.cretu@uniroma2.it>
 *
 * May 25, 2026
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

#pragma once

#include <algorithm>
#include <atomic>
#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <fstream>
#include <limits>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include <rclcpp/rclcpp.hpp>

#include <Eigen/Core>

#include <opencv2/core/mat.hpp>
#include <opencv2/core/types.hpp>

#include <event_camera_codecs/decoder_factory.h>
#include <event_camera_msgs/msg/event_packet.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <std_msgs/msg/header.hpp>
#include <std_srvs/srv/set_bool.hpp>

#include <moment_flow/event_store.hpp>
#include <moment_flow/moment_flow_solver.hpp>
#include <moment_flow/parameter_manager.hpp>

namespace moment_flow
{

using EventPacket = event_camera_msgs::msg::EventPacket;
using SetBool = std_srvs::srv::SetBool;

class EventDetector : public rclcpp::Node
{
public:
  /**
   * @brief Constructor.
   */
  explicit EventDetector(
    const rclcpp::NodeOptions & node_options = rclcpp::NodeOptions());

  /**
   * @brief Destructor.
   */
  ~EventDetector();

private:
  /* Init functions, called in this order by the constructor. */
  void init_parameters();
  void init_cgroups();
  void init_publishers();
  void init_subscribers();
  void init_service_servers();

  /**
   * @brief Activates the node.
   */
  void activate();

  /**
   * @brief Deactivates the node.
   */
  void deactivate();

  /**
   * @brief Enable service callback: activates or deactivates the node.
   *
   * Idempotent: a request matching the current state succeeds without touching
   * the worker thread. Runs on its own mutually exclusive callback group, so
   * two requests can never interleave.
   *
   * @param req Request, true to activate.
   * @param res Response.
   */
  void callback_enable(
    SetBool::Request::SharedPtr req,
    SetBool::Response::SharedPtr res);

  /**
   * @brief Event-packet subscription callback (executor thread).
   *
   * Decodes the packet into an EventStore and hands it to the worker thread
   * via the bounded queue; performs no feature processing itself.
   *
   * @param msg The incoming event packet.
   */
  void callback_event_packet(EventPacket::ConstSharedPtr msg);

  /**
   * @brief Worker thread main loop.
   *
   * Drains the event queue and runs the enabled features (IWE and optical
   * flow) on each chunk, publishing their results. Owns all stateful processors,
   * so they need no locking. Exits when the node is deactivated and the queue
   * has been drained.
   */
  void worker_thread_routine();

  /**
   * @brief Resets stateful processors after a large backward timestamp jump.
   *
   * @param events Decoded events for one packet.
   */
  void handle_stream_discontinuity(const EventStore & events);

  /* Outputs of one dense optical-flow solve over a window. */
  struct FlowResult
  {
    cv::Mat flow_dense_debug;   // dense flow visualization, BGR8
    cv::Mat flow_dense;         // dense image-flow velocity, CV_32FC2 [px/s]
    cv::Mat flow_tiles;         // native tile-grid image-flow velocity, CV_32FC2 [px/s]
    cv::Mat flow_tile_debug;    // native tile-grid flow visualization, BGR8
    cv::Mat flow_events_debug;  // event-supported flow visualization, BGR8
    cv::Mat flow_events;        // flow_dense only where event support exists, CV_32FC2 [px/s]
    cv::Mat iwe;                // Image of Warped Events at the window midpoint, MONO8
  };

  struct FlowTiming
  {
    double total_ms = 0.0;
    double select_events_ms = 0.0;
    double pack_events_ms = 0.0;
    double solve_moments_ms = 0.0;
    double refine_ms = 0.0;
    double render_events_ms = 0.0;
    double iwe_focus_ms = 0.0;
    double tile_flow_ms = 0.0;
    double tile_debug_ms = 0.0;
    double dense_flow_ms = 0.0;
    double flow_debug_ms = 0.0;
    double support_mask_ms = 0.0;
    double events_mask_ms = 0.0;
    double iwe_debug_ms = 0.0;
  };

  struct FlowSaveWindow
  {
    int64_t from_us;
    int64_t to_us;
    int64_t file_index;
  };

  /**
   * @brief Estimates dense optical flow from spatio-temporal moments.
   *
   * Solves a coarse-to-fine tile-field surrogate of CMax from per-cell plane fits
   * and renders both the dense flow field (HSV) and the Image of Warped Events at
   * the window midpoint.
   *
   * Runs on the worker thread.
   *
   * @param window The window of events to estimate the flow from.
   * @return The rendered debug flow (BGR8), dense flow (CV_32FC2),
   * event-supported flow (CV_32FC2), and IWE (MONO8) images.
   */
  FlowResult solve_flow_moment(
    const EventStore & window,
    std::optional<int64_t> t_ref_override_us = std::nullopt);

  /**
   * @brief Opens the end-to-end timing CSV log, if `timing_log_path_` is set.
   *
   * Truncates any pre-existing file and writes the header row. No-op (log
   * stays disabled) if the path is empty or cannot be opened.
   */
  void prepare_timing_log();

  /**
   * @brief Appends one row to the timing CSV log.
   *
   * No-op if the log is disabled. Always called regardless of `debug_`: the
   * end-to-end solve time and coarse timing breakdown are useful data, not
   * debug diagnostics.
   */
  void log_timing(
    int64_t from_us,
    int64_t to_us,
    std::size_t num_events,
    const FlowTiming & timing);

  /**
   * @brief Loads the optional benchmark-save timestamp schedule.
   *
   * If a DSEC-style timestamp file is configured, saves are produced at the
   * ground-truth cadence and named by the DSEC image index. Each estimate still
   * uses the ordinary max_window_ms_ algorithm window at the start of the
   * corresponding ground-truth interval. If no timestamp file is configured,
   * saving falls back to every ordinary max_window_ms_ window.
   */
  void prepare_flow_saving();

  /**
   * @brief Processes one chunk using the DSEC benchmark-save schedule.
   *
   * Splits incoming events so the estimator runs over max_window_ms_ from
   * the start of each ground-truth interval, then skips ahead to the next
   * scheduled save. This keeps the algorithm window independent from the
   * ground-truth cadence.
   *
   * @return Events after the final scheduled save, so ordinary publishing can
   * continue after benchmark output is complete.
   */
  EventStore accumulate_scheduled_flow(
    const EventStore & events,
    const std_msgs::msg::Header & header);

  /**
   * @brief Saves both the dense and event-sparse flow fields as DSEC PNGs.
   *
   * Writes flow_dense to the "dense" subdirectory. When events_enabled_
   * is true, also writes flow_events to the "sparse" subdirectory.
   */
  void save_flow_results(
    const FlowResult & res,
    int64_t file_index,
    int64_t from_us,
    int64_t to_us);

  /**
   * @brief Saves a per-pixel image-flow velocity field in DSEC 16-bit PNG format.
   *
   * The velocity is converted to displacement using the exact interval
   * duration, then encoded as RGB: flow_x, flow_y, valid. OpenCV writes BGR, so
   * the in-memory matrix uses B=valid, G=flow_y, R=flow_x. Non-finite pixels
   * (e.g. unsupported cells in flow_events) are written with valid=0. Files are
   * written under save_output_dir_/<subdir>.
   */
  void save_flow_png(
    const cv::Mat & flow_velocity,
    const std::string & subdir,
    bool empty_is_invalid,
    int64_t file_index,
    int64_t from_us,
    int64_t to_us);

  /**
   * @brief Allocates the resolution-dependent processors on the first packet.
   *
   * @param width Sensor width [px].
   * @param height Sensor height [px].
   */
  void lazy_init(int width, int height);

  /**
   * @brief Rebuilds every stateful processor after a stream discontinuity.
   */
  void reset_state();

  /**
   * @brief Publishes an image if it is non-empty, stamping it with a header.
   *
   * @param pub Target image publisher.
   * @param img Image to publish; ignored if empty.
   * @param encoding sensor_msgs image encoding (e.g. BGR8, MONO8).
   * @param header Header to stamp onto the message.
   */
  void publish_image(
    const rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr & pub,
    const cv::Mat & img,
    const std::string & encoding,
    const std_msgs::msg::Header & header);

  /* Builds an EventStore from event_camera_codecs decoded events (ns -> us).
   * Accumulates into a vector, then sorts before handing it to the worker. */
  class EventStoreBuilder : public event_camera_codecs::EventProcessor
  {
public:
    EventStoreBuilder() = default;

    void eventCD(uint64_t sensor_time, uint16_t ex, uint16_t ey, uint8_t) override
    {
      events_.emplace_back(
        static_cast<int64_t>(sensor_time / 1000),
        static_cast<int16_t>(ex),
        static_cast<int16_t>(ey));
    }

    // event_camera_codecs changed this hook from void to bool across releases;
    // CMake probes the installed header and defines the macro accordingly. The
    // bool tells the decoder whether to keep going, so it is always true: this
    // node ignores external triggers, it does not want decoding to stop.
#ifdef MOMENT_FLOW_EXT_TRIGGER_RETURNS_BOOL
    bool eventExtTrigger(uint64_t, uint8_t, uint8_t) override {return true;}
#else
    void eventExtTrigger(uint64_t, uint8_t, uint8_t) override {}
#endif

    void finished() override {}
    void rawData(const char *, size_t) override {}

    EventStore takeStore()
    {
      std::stable_sort(
        events_.begin(), events_.end(),
        [](const Event & a, const Event & b) {
          return a.timestamp() < b.timestamp();
        });
      return EventStore(std::move(events_));
    }

private:
    std::vector<Event> events_;
  };

  /* One unit of work transferred from the subscription callback to the worker
   * thread: the decoded events plus the metadata needed to process and stamp
   * the outputs. */
  struct EventChunk
  {
    EventStore events;
    std_msgs::msg::Header header;
    int width;
    int height;
  };

  /* Parameters: declared with descriptors, mirrored into the members below. */
  std::unique_ptr<ParameterManager> pmanager_;

  /* Callback Groups. */
  rclcpp::CallbackGroup::SharedPtr cgroup_enable_;
  rclcpp::CallbackGroup::SharedPtr cgroup_event_packet_;

  /* Publishers. */
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr pub_flow_dense_debug_;
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr pub_flow_dense_;
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr pub_flow_tiles_;
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr pub_flow_tile_debug_;
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr pub_flow_events_debug_;
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr pub_flow_events_;
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr pub_iwe_;

  /* Subscribers. */
  rclcpp::Subscription<EventPacket>::SharedPtr sub_event_packet_;

  /* Service servers. */
  rclcpp::Service<SetBool>::SharedPtr server_enable_;

  /* Decoder. */
  event_camera_codecs::DecoderFactory<EventPacket, EventStoreBuilder> decoder_factory_;

  /* Resolution and stream state. */
  cv::Size res_;
  int64_t stream_high_us_{std::numeric_limits<int64_t>::lowest()};

  /* Optical-flow state. Events accumulate here until the time span reaches
   * max_window_ms_, at which point the moment-flow estimator solves the
   * whole batch. */
  EventStore flow_accum_;
  int64_t flow_accum_first_us_{std::numeric_limits<int64_t>::max()};
  int64_t flow_accum_last_us_{std::numeric_limits<int64_t>::lowest()};
  /* Previous window's finest-scale tile flow field and its per-side tile count,
   * used to warm-start the next window. Empty (prev_flow_tiles_ == 0) until the
   * first window has been solved. */
  Eigen::VectorXf prev_flow_field_;
  int prev_flow_tiles_{0};
  std::optional<flow::MomentFlow> moment_flow_;
  std::vector<FlowSaveWindow> flow_save_windows_;
  std::size_t flow_save_next_window_{0};
  int64_t flow_save_sequence_index_{0};
  bool flow_save_prepared_{false};

  /**
   * End of the last scheduled estimation interval, or a negative value while no
   * scheduled window has been closed yet. Gap filling needs it to measure how
   * much of the stream sits between two exports.
   */
  int64_t flow_save_prev_estimate_end_us_{-1};

  /* Node parameters. */
  bool    autostart_;
  bool    iwe_enabled_;
  bool    publish_flow_hsv_;
  bool    events_enabled_;
  bool    debug_;
  double  max_window_ms_;
  int64_t max_solve_events_;
  int64_t num_threads_;
  int64_t num_scales_;
  int64_t cell_size_px_;
  double  cell_min_mass_;
  double  cell_min_lambda_;
  double  cell_max_residual_ratio_;
  double  tile_min_mass_;
  int64_t tile_min_cells_;
  double  tile_min_lambda_;
  double  aperture_ratio_;
  double  tikhonov_eps_;
  double  prior_lambda_;
  double  reg_lambda_;
  int64_t reg_sweeps_;
  double  reg_sigma_;
  int64_t smooth_sweeps_;
  double  smooth_beta_;
  bool    refine_enabled_;
  int64_t refine_iters_;
  bool track_enabled_;
  int64_t iwe_scale_;
  double  max_speed_px_s_;
  bool save_enabled_;
  std::string save_output_dir_;
  std::string save_timestamp_file_;
  bool save_clear_output_;
  bool save_gap_fill_;
  int64_t save_first_index_;
  int64_t save_index_step_;
  std::string timing_log_path_;

  /* End-to-end timing CSV log (open for the lifetime of one activation). */
  std::ofstream timing_log_stream_;
  bool timing_log_ready_{false};

  /* Threads. */
  std::thread thread_worker_;

  /* Event transfer queue (producer: callback, consumer: worker). */
  std::mutex queue_mutex_;
  std::condition_variable queue_cv_;
  std::deque<EventChunk> queue_;

  /* Synchronization primitives. */
  std::atomic<bool> running_{false};
};

} // namespace moment_flow
