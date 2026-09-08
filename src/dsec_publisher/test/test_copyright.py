"""Every source file carries the Apache-2.0 notice."""

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

import unittest

from ament_copyright.main import main


class TestCopyright(unittest.TestCase):
    """Every source file carries the Apache-2.0 notice."""

    def test_copyright(self):
        """Run the linter over the whole package."""
        self.assertEqual(main(argv=[]), 0, 'Copyright errors')
