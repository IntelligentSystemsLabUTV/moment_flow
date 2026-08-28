/**
 * Moment Flow stream-discontinuity handling.
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

#include "moment_flow/event_detector.hpp"

#include <algorithm>
#include <cstdint>

namespace moment_flow
{

namespace
{

constexpr int64_t kTimeResetThresholdUs = 100'000;

}  // namespace

void EventDetector::handle_stream_discontinuity(const EventStore & events)
{
  if (events.isEmpty()) {
    return;
  }

  const int64_t low_us = events.getLowestTime();
  if (low_us < stream_high_us_ &&
    stream_high_us_ - low_us > kTimeResetThresholdUs)
  {
    RCLCPP_WARN(get_logger(), "Event timestamps jumped back; resetting state");
    reset_state();
  }

  stream_high_us_ = std::max(stream_high_us_, events.getHighestTime());
}

}  // namespace moment_flow
