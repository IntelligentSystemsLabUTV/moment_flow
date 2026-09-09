#!/usr/bin/env bash
# Run MomentFlow ablation variants over a sequence set, inside the DUA container.
#
# Usage:
#   run_all.sh [SET_OR_SEQUENCE] [TIER...]
#
#   run_all.sh S1 removal p1     # sweep tiers on the 5-sequence set
#   run_all.sh S3 removal        # component-removal table on the full train split
#   run_all.sh thun_00_a         # every tier on one sequence
#
# Variants run one at a time: concurrent runs would make the timing columns
# meaningless, and the replay saturates several cores on its own.
#
# Environment:
#   KEEP_PREDICTIONS   set to 1 to keep prediction PNGs after scoring
#   SKIP_DONE          set to 1 to skip variants that already have a dense JSON
#   NO_REFERENCE       set to 1 to leave the reference variant out of the sweep
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

# Workspace root. Defaults to the path used for the published runs; override
# MOMENTFLOW_WS to run this tooling from another workspace or from the
# MomentFlow repository itself.
WS="${MOMENTFLOW_WS:-/home/neo/workspace}"
HERE="$WS/tools/momentflow_ablation"
TARGET=${1:-S1}
shift || true
TIERS=("$@")

tier_args=()
for t in "${TIERS[@]:-}"; do
  [[ -n "$t" ]] && tier_args+=(--tier "$t")
done

# The reference is normally swept alongside the tiers. Suppress it when the tier
# already carries its own control run, so an existing reference directory backing
# a published table is not half-refreshed. Set inside the container command, not
# on the host: dua exec does not forward the host environment.
[[ -n "${NO_REFERENCE:-}" ]] && tier_args+=(--no-reference)

if [[ "$TARGET" == S[0-9] ]]; then
  set_args=(--set "$TARGET")
else
  set_args=(--sequence "$TARGET")
fi

# Two concurrent sweeps write to the same run directories, and because every
# variant sets save_clear_output they delete each other's predictions
# mid-run. The result is silently truncated PNG sets and meaningless metrics
# rather than a crash, so refuse to start a second sweep outright.
LOCK="$WS/logs/ablation/.sweep.lock"
mkdir -p "$(dirname "$LOCK")"
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "FATAL: another sweep already holds $LOCK"
  echo "       running: $(cat "$LOCK" 2>/dev/null)"
  exit 1
fi
printf 'pid=%s target=%s tiers=%s started=%s\n' \
  "$$" "$TARGET" "${TIERS[*]:-all}" "$(date -Iseconds)" >&9

mapfile -t sequences < <(python3 "$HERE/variants.py" "${set_args[@]}" --list-sequences)
mapfile -t variants < <(python3 "$HERE/variants.py" "${tier_args[@]+"${tier_args[@]}"}" --list | cut -f1)

echo ">>> target=$TARGET tiers=${TIERS[*]:-all}"
echo ">>> ${#variants[@]} variants x ${#sequences[@]} sequences = $(( ${#variants[@]} * ${#sequences[@]} )) runs"

# Missing ground truth is worth catching before a multi-hour run, not during it.
missing=()
for seq in "${sequences[@]}"; do
  [[ -s "$WS/logs/dsec/$seq/events_left/events.h5" ]] || missing+=("$seq:events")
  [[ -s "$WS/logs/dsec/$seq/optical_flow_forward/${seq}_optical_flow_forward_timestamps.txt" ]] \
    || missing+=("$seq:timestamps")
done
if [[ ${#missing[@]} -gt 0 ]]; then
  echo "FATAL: missing data: ${missing[*]}"
  exit 1
fi

python3 "$HERE/variants.py" "${set_args[@]}" "${tier_args[@]+"${tier_args[@]}"}" || exit 1

n=0
total=$(( ${#variants[@]} * ${#sequences[@]} ))
for v in "${variants[@]}"; do
  for seq in "${sequences[@]}"; do
    n=$((n + 1))
    run_dir="$WS/logs/ablation/$seq/$v"
    if [[ -n "${SKIP_DONE:-}" && -f "$run_dir/dense_benchmark.json" ]]; then
      echo "[$n/$total] skip $v/$seq"
      continue
    fi
    echo "======== [$n/$total] $v / $seq ========"
    bash "$HERE/run_variant.sh" "$v" "$seq" 2>&1 \
      | grep -E '^>>>|EPE:|AE:|1PE|frames:|valid pixels:|FATAL'
  done
done

echo ">>> ALL DONE"
