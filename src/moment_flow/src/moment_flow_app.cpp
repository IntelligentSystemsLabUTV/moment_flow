/**
 * Moment Flow standalone application.
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

#include <cstdlib>
#include <memory>

#include <rclcpp/rclcpp.hpp>

#include <moment_flow/event_detector.hpp>

int main(int argc, char ** argv)
{
  // rclcpp::init installs the SIGINT and SIGTERM handlers that break the spin
  rclcpp::init(argc, argv);

  auto node = std::make_shared<moment_flow::EventDetector>();

  // One thread per callback group: the event-packet callback must not be held
  // up by an enable request, and vice versa
  rclcpp::executors::MultiThreadedExecutor executor;
  executor.add_node(node);
  executor.spin();

  // Destroy the node before shutting the context down, so its destructor can
  // still join the worker thread and log
  executor.remove_node(node);
  node.reset();

  rclcpp::shutdown();
  return EXIT_SUCCESS;
}
