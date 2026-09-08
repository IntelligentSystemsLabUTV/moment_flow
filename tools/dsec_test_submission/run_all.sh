#!/usr/bin/env bash
# Produce the whole DSEC-Flow test-split submission, inside the DUA container.
#
# Usage:
#   run_all.sh [SEQUENCE...]      # default: all seven test sequences
#
# Environment:
#   SKIP_DONE  set to 1 to skip sequences whose prediction set is already complete
#
# Alexandru Cretu <alexandru.cretu@uniroma2.it>
#
# August 26, 2026

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
HERE="$WS/tools/dsec_test_submission"

if [[ $# -gt 0 ]]; then
  sequences=("$@")
else
  mapfile -t sequences < <(python3 -c "
import sys; sys.path.insert(0, '$HERE')
from make_configs import TEST_SEQUENCES
print('\n'.join(TEST_SEQUENCES))")
fi

# One replay at a time. Concurrent runs would share the CPU and change how many
# events reach each solver, which is the load dependence documented for the
# training split; on a submission that cannot be re-scored locally it is not a
# risk worth taking.
LOCK="$WS/logs/dsec_test/.run.lock"
mkdir -p "$(dirname "$LOCK")"
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "FATAL: another test run already holds $LOCK"
  exit 1
fi

missing=()
for seq in "${sequences[@]}"; do
  [[ -s "$WS/logs/dsec/$seq/events_left/events.h5" ]] || missing+=("$seq:events")
  [[ -s "$WS/logs/dsec/$seq/test_forward_flow/$seq.csv" ]] || missing+=("$seq:schedule")
done
if [[ ${#missing[@]} -gt 0 ]]; then
  echo "FATAL: missing data: ${missing[*]}"
  echo "       run bin/download_dsec_test_sequence.sh --all first"
  exit 1
fi

python3 "$HERE/make_configs.py" $(printf -- '--sequence %s ' "${sequences[@]}") || exit 1

n=0
total=${#sequences[@]}
for seq in "${sequences[@]}"; do
  n=$((n + 1))
  run_dir="$WS/logs/dsec_test/$seq"
  expected=$(cat "$run_dir/expected.txt" 2>/dev/null || echo 0)
  have=$(find "$run_dir/dense" -name '*.png' 2>/dev/null | wc -l)
  if [[ -n "${SKIP_DONE:-}" && "$expected" -gt 0 && "$have" -ge "$expected" ]]; then
    echo "[$n/$total] skip $seq ($have/$expected)"
    continue
  fi
  echo "======== [$n/$total] $seq ========"
  bash "$HERE/run_test_sequence.sh" "$seq" 2>&1 | grep -E '^>>>|FATAL|WARNING'
done

echo ">>> ALL SEQUENCES DONE"
python3 "$HERE/package_submission.py" --verify-only --deep
