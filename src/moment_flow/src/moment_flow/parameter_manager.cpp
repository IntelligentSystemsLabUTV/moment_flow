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

#include "moment_flow/parameter_manager.hpp"

#include <stdexcept>
#include <utility>

#include <rcl_interfaces/msg/floating_point_range.hpp>
#include <rcl_interfaces/msg/integer_range.hpp>
#include <rcl_interfaces/msg/parameter_descriptor.hpp>

namespace moment_flow
{

namespace
{

/* Fills the fields every descriptor carries, whatever the type. */
rcl_interfaces::msg::ParameterDescriptor make_descriptor(
  const std::string & name,
  rclcpp::ParameterType type,
  const std::string & description,
  const std::string & constraints,
  bool read_only)
{
  rcl_interfaces::msg::ParameterDescriptor descriptor;
  descriptor.name = name;
  descriptor.type = static_cast<uint8_t>(type);
  descriptor.description = description;
  descriptor.additional_constraints = constraints;
  descriptor.read_only = read_only;
  descriptor.dynamic_typing = false;
  return descriptor;
}

}  // namespace

ParameterManager::ParameterManager(rclcpp::Node * node)
: node_(node)
{
  if (!node_) {
    throw std::invalid_argument("ParameterManager: node pointer cannot be null");
  }

  callback_handle_ = node_->add_on_set_parameters_callback(
    std::bind(
      &ParameterManager::on_set_parameters,
      this,
      std::placeholders::_1));
  if (!callback_handle_) {
    throw std::runtime_error("ParameterManager: could not register the parameter callback");
  }
}

ParameterManager::~ParameterManager()
{
  node_->remove_on_set_parameters_callback(callback_handle_.get());
  std::scoped_lock<std::mutex> lock(entries_mutex_);
  entries_.clear();
}

void ParameterManager::add_entry(
  const std::string & name,
  rclcpp::ParameterType type,
  void * var)
{
  std::scoped_lock<std::mutex> lock(entries_mutex_);
  if (!entries_.emplace(name, Entry{type, var}).second) {
    throw std::invalid_argument("ParameterManager: parameter '" + name + "' already declared");
  }
}

rcl_interfaces::msg::SetParametersResult ParameterManager::on_set_parameters(
  const std::vector<rclcpp::Parameter> & params)
{
  rcl_interfaces::msg::SetParametersResult result;
  result.successful = true;
  result.reason = "";

  for (const rclcpp::Parameter & p : params) {
    void * var = nullptr;
    {
      std::scoped_lock<std::mutex> lock(entries_mutex_);
      const auto it = entries_.find(p.get_name());
      if (it == entries_.end()) {
        // Not ours: another callback, or another component in the same process
        continue;
      }
      if (p.get_type() != it->second.type) {
        result.successful = false;
        result.reason = "Parameter '" + p.get_name() + "' type mismatch";
        return result;
      }
      var = it->second.var;
    }

    if (!var) {
      continue;
    }

    switch (p.get_type()) {
      case rclcpp::ParameterType::PARAMETER_BOOL:
        *static_cast<bool *>(var) = p.as_bool();
        break;
      case rclcpp::ParameterType::PARAMETER_INTEGER:
        *static_cast<int64_t *>(var) = p.as_int();
        break;
      case rclcpp::ParameterType::PARAMETER_DOUBLE:
        *static_cast<double *>(var) = p.as_double();
        break;
      case rclcpp::ParameterType::PARAMETER_STRING:
        *static_cast<std::string *>(var) = p.as_string();
        break;
      default:
        result.successful = false;
        result.reason = "Parameter '" + p.get_name() + "' has an unsupported type";
        return result;
    }
  }

  return result;
}

void ParameterManager::declare_bool(
  const std::string & name,
  bool default_value,
  const std::string & description,
  const std::string & constraints,
  bool read_only,
  bool * var)
{
  add_entry(name, rclcpp::ParameterType::PARAMETER_BOOL, var);
  const bool effective = node_->declare_parameter(
    name,
    default_value,
    make_descriptor(
      name, rclcpp::ParameterType::PARAMETER_BOOL, description, constraints, read_only));
  if (var) {
    *var = effective;
  }
}

void ParameterManager::declare_integer(
  const std::string & name,
  int64_t default_value,
  int64_t min_value,
  int64_t max_value,
  int64_t step,
  const std::string & description,
  const std::string & constraints,
  bool read_only,
  int64_t * var)
{
  add_entry(name, rclcpp::ParameterType::PARAMETER_INTEGER, var);

  auto descriptor = make_descriptor(
    name, rclcpp::ParameterType::PARAMETER_INTEGER, description, constraints, read_only);
  rcl_interfaces::msg::IntegerRange range;
  range.from_value = min_value;
  range.to_value = max_value;
  range.step = step;
  descriptor.integer_range = {range};

  const int64_t effective = node_->declare_parameter(name, default_value, descriptor);
  if (var) {
    *var = effective;
  }
}

void ParameterManager::declare_double(
  const std::string & name,
  double default_value,
  double min_value,
  double max_value,
  double step,
  const std::string & description,
  const std::string & constraints,
  bool read_only,
  double * var)
{
  add_entry(name, rclcpp::ParameterType::PARAMETER_DOUBLE, var);

  auto descriptor = make_descriptor(
    name, rclcpp::ParameterType::PARAMETER_DOUBLE, description, constraints, read_only);
  rcl_interfaces::msg::FloatingPointRange range;
  range.from_value = min_value;
  range.to_value = max_value;
  range.step = step;
  descriptor.floating_point_range = {range};

  const double effective = node_->declare_parameter(name, default_value, descriptor);
  if (var) {
    *var = effective;
  }
}

void ParameterManager::declare_string(
  const std::string & name,
  const std::string & default_value,
  const std::string & description,
  const std::string & constraints,
  bool read_only,
  std::string * var)
{
  add_entry(name, rclcpp::ParameterType::PARAMETER_STRING, var);
  const std::string effective = node_->declare_parameter(
    name,
    default_value,
    make_descriptor(
      name, rclcpp::ParameterType::PARAMETER_STRING, description, constraints, read_only));
  if (var) {
    *var = effective;
  }
}

}  // namespace moment_flow
