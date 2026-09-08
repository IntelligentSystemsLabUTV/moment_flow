/**
 * Node parameter declaration with descriptors and member synchronization.
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

#pragma once

#include <cstdint>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

#include <rcl_interfaces/msg/set_parameters_result.hpp>
#include <rclcpp/rclcpp.hpp>

namespace moment_flow
{

/**
 * @brief Declares node parameters and keeps plain member variables in sync.
 *
 * Each parameter is declared with a full descriptor, so `ros2 param describe`
 * reports its documentation and rclcpp itself enforces the declared range and
 * type. The address passed on declaration is written once with the effective
 * startup value and then again on every accepted runtime update, so the node
 * can read parameters as ordinary members instead of querying the parameter
 * server on every use.
 *
 * Built on rclcpp only: the node stays a plain rclcpp::Node.
 */
class ParameterManager
{
public:
  /**
   * @brief Constructor: registers the on-set-parameters callback.
   *
   * @param node Node to declare parameters on; must outlive this object.
   * @throws std::invalid_argument if node is null.
   * @throws std::runtime_error if the callback cannot be registered.
   */
  explicit ParameterManager(rclcpp::Node * node);

  /**
   * @brief Destructor: removes the on-set-parameters callback.
   */
  ~ParameterManager();

  ParameterManager(const ParameterManager &) = delete;
  ParameterManager & operator=(const ParameterManager &) = delete;

  /**
   * @brief Declares a boolean parameter.
   *
   * @param name Parameter name.
   * @param default_value Value used when no override is provided.
   * @param description What the parameter does.
   * @param constraints Human-readable constraints.
   * @param read_only Whether the value is fixed after startup.
   * @param var Member kept in sync; may be nullptr.
   */
  void declare_bool(
    const std::string & name,
    bool default_value,
    const std::string & description,
    const std::string & constraints,
    bool read_only,
    bool * var);

  /**
   * @brief Declares an integer parameter with an inclusive range.
   *
   * @param name Parameter name.
   * @param default_value Value used when no override is provided.
   * @param min_value Lowest accepted value.
   * @param max_value Highest accepted value.
   * @param step Accepted increment, 0 for none.
   * @param description What the parameter does.
   * @param constraints Human-readable constraints.
   * @param read_only Whether the value is fixed after startup.
   * @param var Member kept in sync; may be nullptr.
   */
  void declare_integer(
    const std::string & name,
    int64_t default_value,
    int64_t min_value,
    int64_t max_value,
    int64_t step,
    const std::string & description,
    const std::string & constraints,
    bool read_only,
    int64_t * var);

  /**
   * @brief Declares a floating-point parameter with an inclusive range.
   *
   * @param name Parameter name.
   * @param default_value Value used when no override is provided.
   * @param min_value Lowest accepted value.
   * @param max_value Highest accepted value.
   * @param step Accepted increment, 0.0 for none.
   * @param description What the parameter does.
   * @param constraints Human-readable constraints.
   * @param read_only Whether the value is fixed after startup.
   * @param var Member kept in sync; may be nullptr.
   */
  void declare_double(
    const std::string & name,
    double default_value,
    double min_value,
    double max_value,
    double step,
    const std::string & description,
    const std::string & constraints,
    bool read_only,
    double * var);

  /**
   * @brief Declares a string parameter.
   *
   * @param name Parameter name.
   * @param default_value Value used when no override is provided.
   * @param description What the parameter does.
   * @param constraints Human-readable constraints.
   * @param read_only Whether the value is fixed after startup.
   * @param var Member kept in sync; may be nullptr.
   */
  void declare_string(
    const std::string & name,
    const std::string & default_value,
    const std::string & description,
    const std::string & constraints,
    bool read_only,
    std::string * var);

private:
  /* One declared parameter: the type it was declared with and the member that
   * mirrors it. */
  struct Entry
  {
    rclcpp::ParameterType type;
    void * var;
  };

  /**
   * @brief Mirrors accepted updates into the registered members.
   *
   * Rejects a type mismatch; range and step are enforced by rclcpp from the
   * descriptor, so they are not re-checked here.
   */
  rcl_interfaces::msg::SetParametersResult on_set_parameters(
    const std::vector<rclcpp::Parameter> & params);

  /**
   * @brief Registers a parameter before declaring it on the node.
   *
   * @throws std::invalid_argument if the name is already registered.
   */
  void add_entry(const std::string & name, rclcpp::ParameterType type, void * var);

  rclcpp::Node * node_;
  rclcpp::node_interfaces::OnSetParametersCallbackHandle::SharedPtr callback_handle_;

  /* Guards entries_. Never held across a call into the node, so the callback
   * that declaring a parameter triggers cannot deadlock. */
  std::mutex entries_mutex_;
  std::unordered_map<std::string, Entry> entries_;
};

}  // namespace moment_flow
