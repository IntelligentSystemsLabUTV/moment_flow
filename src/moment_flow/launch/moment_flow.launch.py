"""
Moment Flow launch file.

dotX Automation s.r.l. <info@dotxautomation.com>

May 25, 2025
"""

# Copyright 2024 dotX Automation s.r.l.
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

import os
from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import ComposableNodeContainer
from launch_ros.descriptions import ComposableNode


def generate_launch_description():
    ld = LaunchDescription()

    # Build config file path
    default_config = os.path.join(
        get_package_share_directory('moment_flow'),
        'config',
        'moment_flow.yaml'
    )
    # Declare launch arguments
    ns = LaunchConfiguration('namespace')
    ns_launch_arg = DeclareLaunchArgument(
        'namespace',
        default_value='')
    ld.add_action(ns_launch_arg)

    # Overriding the parameter file keeps ablation variants out of the tracked
    # deployment config: reproducibility through configuration alone
    config = LaunchConfiguration('config')
    config_launch_arg = DeclareLaunchArgument(
        'config',
        default_value=default_config)
    ld.add_action(config_launch_arg)

    container = ComposableNodeContainer(
        name="moment_flow_container",
        namespace=ns,
        package="dua_app_management",
        executable="dua_component_container_mt",
        emulate_tty=True,
        output='both',
        log_cmd=True,
        composable_node_descriptions=[
            # Moment Flow
            ComposableNode(
                package='moment_flow',
                plugin='moment_flow::EventDetector',
                namespace=ns,
                name='moment_flow',
                parameters=[config],
                remappings=[
                    ('/event_packet', '/event_camera/events')
                ],
                extra_arguments=[{'use_intra_process_comms': True}],
            ),
        ],
    )
    ld.add_action(container)

    return ld
