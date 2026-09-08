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

from glob import glob
import os

from setuptools import find_packages, setup

package_name = 'dsec_publisher'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    author='Alexandru Cretu',
    author_email='alexandru.cretu@uniroma2.it',
    maintainer='Alexandru Cretu',
    maintainer_email='alexandru.cretu@uniroma2.it',
    description=('Replays DSEC event HDF5 recordings as event_camera_msgs/EventPacket '
                 'for offline benchmarking.'),
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'dsec_publisher = dsec_publisher.dsec_publisher_node:main',
        ],
    },
)
