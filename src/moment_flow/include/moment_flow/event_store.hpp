/**
 * Internal event representation and temporally ordered storage.
 *
 * dotX Automation s.r.l. <info@dotxautomation.com>
 *
 * May 25, 2026
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

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <iterator>
#include <limits>
#include <stdexcept>
#include <utility>
#include <vector>

namespace moment_flow
{

struct Event
{
  int64_t t_us;
  int16_t x_px;
  int16_t y_px;

  Event() = default;

  Event(int64_t timestamp_us, int16_t x, int16_t y)
  : t_us(timestamp_us),
    x_px(x),
    y_px(y)
  {}

  int64_t timestamp() const { return t_us; }
  int16_t x() const { return x_px; }
  int16_t y() const { return y_px; }
};

class EventStore
{
public:
  using container_type = std::vector<Event>;
  using iterator = container_type::iterator;
  using const_iterator = container_type::const_iterator;

  EventStore() = default;

  explicit EventStore(container_type events)
  : events_(std::move(events))
  {}

  bool isEmpty() const { return events_.empty(); }
  std::size_t size() const { return events_.size(); }

  iterator begin() { return events_.begin(); }
  iterator end() { return events_.end(); }
  const_iterator begin() const { return events_.begin(); }
  const_iterator end() const { return events_.end(); }

  const Event & front() const { return events_.front(); }
  const Event & back() const { return events_.back(); }

  void push_back(const Event & event) { events_.push_back(event); }

  int64_t getLowestTime() const
  {
    return events_.empty() ? std::numeric_limits<int64_t>::max() : events_.front().timestamp();
  }

  int64_t getHighestTime() const
  {
    return events_.empty() ? std::numeric_limits<int64_t>::lowest() : events_.back().timestamp();
  }

  void add(const EventStore & other)
  {
    if (other.isEmpty()) {
      return;
    }
    if (!events_.empty() && other.getLowestTime() < getHighestTime()) {
      throw std::out_of_range("EventStore::add received out-of-order events");
    }
    events_.insert(events_.end(), other.begin(), other.end());
  }

  void add(EventStore && other)
  {
    if (other.isEmpty()) {
      return;
    }
    if (!events_.empty() && other.getLowestTime() < getHighestTime()) {
      throw std::out_of_range("EventStore::add received out-of-order events");
    }
    if (events_.empty()) {
      events_ = std::move(other.events_);
      return;
    }
    events_.insert(
      events_.end(),
      std::make_move_iterator(other.events_.begin()),
      std::make_move_iterator(other.events_.end()));
    other.events_.clear();
  }

private:
  container_type events_;
};

}  // namespace moment_flow
