# Endpoint-error visualizations for qualitative inspection.
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
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def save_epe_image(
  path: str | Path,
  epe_map: np.ndarray,
  valid_mask: np.ndarray,
  *,
  max_error: float = 10.0,
) -> None:
  path = Path(path)
  scaled = np.zeros(epe_map.shape, dtype=np.uint8)
  if max_error <= 0:
    raise ValueError("max_error must be positive")
  clipped = np.clip(epe_map / max_error, 0.0, 1.0)
  scaled[valid_mask] = np.rint(255.0 * clipped[valid_mask]).astype(np.uint8)
  color = cv2.applyColorMap(scaled, cv2.COLORMAP_TURBO)
  color[~valid_mask] = 0
  path.parent.mkdir(parents=True, exist_ok=True)
  if not cv2.imwrite(str(path), color):
    raise OSError(f"Could not write error image: {path}")
