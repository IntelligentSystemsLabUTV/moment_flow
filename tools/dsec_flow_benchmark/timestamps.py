# Parsing of DSEC optical-flow timestamp files.
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

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class FlowTiming:
  from_us: int
  to_us: int
  index: int | None = None

  @property
  def midpoint_us(self) -> int:
    return (self.from_us + self.to_us) // 2

  @property
  def dt_us(self) -> int:
    return self.to_us - self.from_us

  def key(self, name: str) -> int:
    if name == "from":
      return self.from_us
    if name == "to":
      return self.to_us
    if name == "midpoint":
      return self.midpoint_us
    raise ValueError(f"Unknown timestamp key: {name}")


def find_timestamp_file(flow_dir: str | Path) -> Path | None:
  flow_dir = Path(flow_dir)
  candidates = []
  for pattern in ("*timestamp*.txt", "*timestamp*.csv", "*.csv"):
    candidates.extend(flow_dir.glob(pattern))
  candidates = sorted({path for path in candidates if path.is_file()})
  for candidate in candidates:
    try:
      load_timestamps(candidate)
    except ValueError:
      continue
    return candidate
  return None


def load_timestamps(path: str | Path) -> list[FlowTiming]:
  path = Path(path)
  rows: list[FlowTiming] = []
  with path.open("r", encoding="utf-8") as handle:
    for line_no, raw_line in enumerate(handle, start=1):
      line = raw_line.strip()
      if not line or line.startswith("#"):
        continue
      parts = [part for part in re.split(r"[\s,]+", line) if part]
      try:
        values = [int(float(part)) for part in parts]
      except ValueError:
        # Header line, for example: from_timestamp_us,to_timestamp_us,file_index
        continue

      if len(values) == 1:
        rows.append(FlowTiming(values[0], values[0], None))
      elif len(values) >= 2:
        rows.append(FlowTiming(values[0], values[1], values[2] if len(values) >= 3 else None))
      else:
        raise ValueError(f"Could not parse timestamp line {line_no}: {raw_line!r}")

  if not rows:
    raise ValueError(f"No timestamp rows found in {path}")
  return rows
