/**
 * Moment Flow node implementation.
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

#include "moment_flow/event_detector.hpp"

#include <functional>
#include <memory>

namespace moment_flow
{

namespace
{

/* Inputs are reliable: dropping an event packet loses events for good, and the
 * decoder needs the full sequence. Depth 10 absorbs a late worker without
 * pushing the loss into the middleware. */
rclcpp::QoS input_qos()
{
  rclcpp::QoS qos(rclcpp::KeepLast(10));
  qos.reliable();
  qos.durability_volatile();
  return qos;
}

/* Outputs are best effort with depth 1: a visualization consumer wants the
 * latest field, never a backlog. */
rclcpp::QoS image_qos()
{
  rclcpp::QoS qos(rclcpp::KeepLast(1));
  qos.best_effort();
  qos.durability_volatile();
  return qos;
}

}  // namespace

EventDetector::EventDetector(const rclcpp::NodeOptions & node_options)
: Node("moment_flow", node_options)
{
  pmanager_ = std::make_unique<ParameterManager>(this);

  init_parameters();
  init_cgroups();
  init_publishers();
  init_subscribers();
  init_service_servers();

  RCLCPP_INFO(this->get_logger(), "Node initialized");

  if (autostart_) {
    activate();
  }
}

EventDetector::~EventDetector()
{
  deactivate();
}

void EventDetector::init_cgroups()
{
  cgroup_enable_ = create_callback_group(rclcpp::CallbackGroupType::MutuallyExclusive);
  cgroup_event_packet_ = create_callback_group(rclcpp::CallbackGroupType::MutuallyExclusive);
}

void EventDetector::init_subscribers()
{
  rclcpp::SubscriptionOptions options;
  options.callback_group = cgroup_event_packet_;

  sub_event_packet_ = create_subscription<EventPacket>(
    "/event_packet",
    input_qos(),
    std::bind(
      &EventDetector::callback_event_packet,
      this,
      std::placeholders::_1),
    options);
}

void EventDetector::init_publishers()
{
  pub_flow_dense_debug_ = create_publisher<sensor_msgs::msg::Image>(
    "~/flow_dense_debug",
    image_qos());

  pub_flow_dense_ = create_publisher<sensor_msgs::msg::Image>(
    "~/flow_dense",
    image_qos());

  pub_flow_tiles_ = create_publisher<sensor_msgs::msg::Image>(
    "~/flow_tiles",
    image_qos());

  pub_flow_tile_debug_ = create_publisher<sensor_msgs::msg::Image>(
    "~/flow_tile_debug",
    image_qos());

  pub_flow_events_debug_ = create_publisher<sensor_msgs::msg::Image>(
    "~/flow_events_debug",
    image_qos());

  pub_flow_events_ = create_publisher<sensor_msgs::msg::Image>(
    "~/flow_events",
    image_qos());

  pub_iwe_ = create_publisher<sensor_msgs::msg::Image>(
    "~/iwe_image",
    image_qos());
}

void EventDetector::init_service_servers()
{
  server_enable_ = create_service<SetBool>(
    "~/enable",
    std::bind(
      &EventDetector::callback_enable,
      this,
      std::placeholders::_1,
      std::placeholders::_2),
    rclcpp::ServicesQoS(),
    cgroup_enable_);
}

} // namespace moment_flow

#include <rclcpp_components/register_node_macro.hpp>
RCLCPP_COMPONENTS_REGISTER_NODE(moment_flow::EventDetector)
