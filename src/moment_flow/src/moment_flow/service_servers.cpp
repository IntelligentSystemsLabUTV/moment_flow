/**
 * Moment Flow service servers implementation.
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

#include <atomic>

namespace moment_flow
{

void EventDetector::callback_enable(
  SetBool::Request::SharedPtr req,
  SetBool::Response::SharedPtr res)
{
  // Only this callback group ever transitions the node, so reading the flag
  // and acting on it cannot race with another request.
  const bool active = running_.load(std::memory_order_acquire);

  if (req->data == active) {
    res->set__success(true);
    res->set__message("");
    return;
  }

  if (req->data) {
    activate();
  } else {
    deactivate();
  }

  res->set__success(true);
  res->set__message("");
}

}  // namespace moment_flow
