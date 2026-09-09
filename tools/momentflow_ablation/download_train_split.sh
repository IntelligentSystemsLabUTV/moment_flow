#!/usr/bin/env bash
# Fetch the whole DSEC-Flow train split (the 18 sequences with public forward-flow
# ground truth) through bin/download_dsec_sequence.sh, skipping sequences that are
# already complete on disk.
#
# Runs on the host: this is plain wget/unzip work, nothing ROS-related.
#
# Alexandru Cretu <alexandru.cretu@uniroma2.it>
#
# August 24, 2026

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

set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace="$(cd "$here/../.." && pwd)"
dsec_root="${DSEC_ROOT:-$workspace/logs/dsec}"

# The 18 sequences carrying public forward-flow ground truth, ordered smallest
# first so a failure late in the run still leaves most of the split usable.
sequences=(
  thun_00_a
  zurich_city_11_a
  zurich_city_01_a
  zurich_city_02_a
  zurich_city_07_a
  zurich_city_08_a
  zurich_city_05_b
  zurich_city_03_a
  zurich_city_02_d
  zurich_city_06_a
  zurich_city_11_c
  zurich_city_05_a
  zurich_city_11_b
  zurich_city_09_a
  zurich_city_02_e
  zurich_city_10_a
  zurich_city_10_b
  zurich_city_02_c
)

complete() {
  local seq="$1" dir="$dsec_root/$1"
  [[ -s "$dir/events_left/events.h5" ]] || return 1
  [[ -s "$dir/events_left/rectify_map.h5" ]] || return 1
  [[ -s "$dir/optical_flow_forward/${seq}_optical_flow_forward_timestamps.txt" ]] || return 1
  [[ -n "$(find "$dir/optical_flow_forward" -maxdepth 1 -name '*.png' -print -quit 2>/dev/null)" ]] || return 1
  return 0
}

total=${#sequences[@]}
done_n=0
failed=()
for seq in "${sequences[@]}"; do
  done_n=$((done_n + 1))
  if complete "$seq"; then
    echo "[$done_n/$total] SKIP $seq (already complete)"
    continue
  fi
  avail_gib=$(df -BG --output=avail "$dsec_root" | tail -1 | tr -dc '0-9')
  echo "[$done_n/$total] GET  $seq (${avail_gib} GiB free)"
  # The largest sequence needs ~10 GiB transiently, zip plus extracted.
  if [[ "$avail_gib" -lt 15 ]]; then
    echo "ABORT: only ${avail_gib} GiB free, refusing to continue"
    failed+=("$seq(no-space)")
    break
  fi
  if bash "$here/../download_dsec_sequence.sh" "$seq"; then
    echo "[$done_n/$total] OK   $seq"
  else
    echo "[$done_n/$total] FAIL $seq"
    failed+=("$seq")
  fi
done

echo
echo "=== summary ==="
for seq in "${sequences[@]}"; do
  if complete "$seq"; then
    printf '  %-20s ok   %s\n' "$seq" \
      "$(du -sh "$dsec_root/$seq" 2>/dev/null | cut -f1)"
  else
    printf '  %-20s MISSING\n' "$seq"
  fi
done
echo "total: $(du -sh "$dsec_root" 2>/dev/null | cut -f1), free: $(df -h --output=avail "$dsec_root" | tail -1 | tr -d ' ')"
if [[ ${#failed[@]} -gt 0 ]]; then
  echo "failed: ${failed[*]}"
  echo "ALL DONE (with failures)"
  exit 1
fi
echo "ALL DONE"
