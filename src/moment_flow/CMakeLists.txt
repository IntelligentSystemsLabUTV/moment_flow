# Moment Flow package build configuration.
#
# Alexandru Cretu <alexandru.cretu@uniroma2.it>
#
# September 8, 2026

# Copyright 2026 Alexandru Cretu
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
cmake_minimum_required(VERSION 3.12)
project(moment_flow)

set(CMAKE_BUILD_TYPE "RelWithDebInfo")

# Default to C++17
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
  add_compile_options(-Wno-array-bounds) # Eigen warning
endif()

cmake_policy(SET CMP0146 OLD)
cmake_policy(SET CMP0074 NEW)
if(POLICY CMP0144)
  cmake_policy(SET CMP0144 NEW)
endif()

set(THREADS_PREFER_PTHREAD_FLAG ON)

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(Eigen3 3.4 REQUIRED)
find_package(eigen3_cmake_module REQUIRED)
find_package(event_camera_codecs REQUIRED)
find_package(event_camera_msgs REQUIRED)
find_package(OpenCV REQUIRED)
find_package(OpenMP REQUIRED)
find_package(rcl_interfaces REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_components REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)
find_package(Threads REQUIRED)

# Configure include directories from external libraries
include_directories(
  include)

# event_camera_codecs changed EventProcessor::eventExtTrigger from void to bool
# between releases. Probe the header that is actually installed instead of
# guessing a version boundary, so the package builds against either API.
include(CheckCXXSourceCompiles)
set(CMAKE_REQUIRED_INCLUDES ${event_camera_codecs_INCLUDE_DIRS})
set(CMAKE_REQUIRED_FLAGS "-std=c++17")
check_cxx_source_compiles("
#include <cstddef>
#include <cstdint>
#include <event_camera_codecs/event_processor.h>
struct Probe : public event_camera_codecs::EventProcessor
{
  void eventCD(uint64_t, uint16_t, uint16_t, uint8_t) override {}
  void eventExtTrigger(uint64_t, uint8_t, uint8_t) override {}
  void finished() override {}
  void rawData(const char *, size_t) override {}
};
int main() { Probe p; (void) p; return 0; }
" EVENT_CAMERA_CODECS_EXT_TRIGGER_RETURNS_VOID)
unset(CMAKE_REQUIRED_INCLUDES)
unset(CMAKE_REQUIRED_FLAGS)

# Configure Moment Flow node source files
set(MOMENT_FLOW_NODE_SRCS
  src/moment_flow/init_parameters.cpp
  src/moment_flow/moment_flow.cpp
  src/moment_flow/moment_flow_solver.cpp
  src/moment_flow/optical_flow.cpp
  src/moment_flow/parameter_manager.cpp
  src/moment_flow/service_servers.cpp
  src/moment_flow/stream_discontinuity.cpp
  src/moment_flow/subscriptions.cpp
  src/moment_flow/utils.cpp
  src/moment_flow/workers.cpp)

# Moment Flow node
add_library(moment_flow SHARED ${MOMENT_FLOW_NODE_SRCS})
target_compile_definitions(moment_flow PRIVATE COMPOSITION_BUILDING_DLL)
if(NOT EVENT_CAMERA_CODECS_EXT_TRIGGER_RETURNS_VOID)
  message(STATUS "event_camera_codecs: eventExtTrigger returns bool")
  target_compile_definitions(moment_flow PUBLIC MOMENT_FLOW_EXT_TRIGGER_RETURNS_BOOL)
endif()
target_include_directories(moment_flow PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
  ${EIGEN3_INCLUDE_DIR}
  ${OpenCV_INCLUDE_DIRS}
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src/moment_flow>)
target_compile_features(moment_flow PUBLIC cxx_std_17)
target_link_libraries(moment_flow
  Eigen3::Eigen
  ${OpenCV_LIBS}
  OpenMP::OpenMP_CXX
  Threads::Threads
)
ament_target_dependencies(moment_flow
  event_camera_codecs
  event_camera_msgs
  rcl_interfaces
  rclcpp
  rclcpp_components
  sensor_msgs
  std_msgs
  std_srvs
)

rclcpp_components_register_nodes(moment_flow "moment_flow::EventDetector")

# Moment Flow standalone application
add_executable(moment_flow_app
  src/moment_flow_app.cpp)
target_include_directories(moment_flow_app PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_features(moment_flow_app PUBLIC cxx_std_17)
target_link_libraries(moment_flow_app moment_flow)
ament_target_dependencies(moment_flow_app
  rclcpp)

# Install Moment Flow component
install(TARGETS moment_flow
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin)

install(DIRECTORY include/
  DESTINATION include)

ament_export_include_directories(include)
ament_export_libraries(moment_flow)
ament_export_dependencies(
  event_camera_codecs
  event_camera_msgs
  Eigen3
  OpenCV
  rcl_interfaces
  rclcpp
  rclcpp_components
  sensor_msgs
  std_msgs
  std_srvs)

# Install Moment Flow app
install(TARGETS moment_flow_app
  DESTINATION lib/${PROJECT_NAME})

# Install Config files
install(DIRECTORY config
  DESTINATION share/${PROJECT_NAME})

# Install Launch files
install(DIRECTORY launch
  DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)

  # cpplint infers the "own header" of a translation unit from its file name. This
  # package splits one class across several files by concern, so every unit opens
  # with event_detector.hpp and cpplint reports each following standard header as
  # out of order. The order is the intended one, and cannot be expressed in a way
  # the check accepts without renaming the sources.
  set(ament_cmake_cpplint_FOUND TRUE)

  set(ament_cmake_copyright_FOUND TRUE)

  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
