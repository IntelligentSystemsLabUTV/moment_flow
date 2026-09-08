#!/usr/bin/env bash
# Produce the DSEC-Flow test-split prediction set for one sequence.
#
# Replays the full left event stream through moment_flow with the reported
# configuration and exports one dense flow PNG per interval of the official
# evaluation schedule. There is no ground truth for this split, so nothing is
# scored here: the only checks are that every scheduled interval produced a file
# and that the file names match the indices the evaluation server expects.
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
SEQUENCE=${1:?usage: run_test_sequence.sh SEQUENCE}
REALTIME_FACTOR=${REALTIME_FACTOR:-1.0}
SETTLE_S=${SETTLE_S:-12}
STALL_LIMIT_S=${STALL_LIMIT_S:-60}
REPLAY_TIMEOUT=${REPLAY_TIMEOUT:-2400}

RUN_DIR="$WS/logs/dsec_test/$SEQUENCE"
SCHEDULE="$WS/logs/dsec/$SEQUENCE/test_forward_flow/$SEQUENCE.csv"
H5="$WS/logs/dsec/$SEQUENCE/events_left/events.h5"
CONFIG="$RUN_DIR/config.yaml"

[[ -f "$CONFIG" ]]   || { echo "FATAL: missing $CONFIG (run make_configs.py first)"; exit 1; }
[[ -f "$SCHEDULE" ]] || { echo "FATAL: missing $SCHEDULE"; exit 1; }
[[ -s "$H5" ]]       || { echo "FATAL: missing $H5"; exit 1; }

EXPECTED=$(grep -cvE '^\s*(#|$)' "$SCHEDULE")
echo ">>> sequence=$SEQUENCE expected=$EXPECTED rf=$REALTIME_FACTOR"

set +u
source /opt/ros/jazzy/setup.bash
source "$WS/install/setup.bash"
set -u

pids=()
cleanup() {
  for p in "${pids[@]:-}"; do kill -INT -- -"$p" 2>/dev/null; done
  sleep 2
  pkill -INT -f component_container_mt 2>/dev/null
  pkill -INT -f dsec_publisher 2>/dev/null
  sleep 1
  pkill -KILL -f component_container_mt 2>/dev/null
  pkill -KILL -f dsec_publisher 2>/dev/null
}
trap cleanup EXIT

setsid ros2 launch moment_flow moment_flow.launch.py config:="$CONFIG" \
  > "$RUN_DIR/detector.log" 2>&1 &
pids+=($!)
sleep "$SETTLE_S"

setsid ros2 launch dsec_publisher dsec_publisher.launch.py \
  sequence:="$SEQUENCE" events_h5:="$H5" topic:=/event_camera/events \
  realtime_factor:="$REALTIME_FACTOR" publish_imu:=false publish_tf:=false \
  publish_lidar:=false \
  > "$RUN_DIR/dsec.log" 2>&1 &
pids+=($!)
PUB_PID=$!

# The test schedule is sparse: intervals are 500 ms apart and some sequences have
# multi-second holes, so the last scheduled interval can sit far from the end of
# the stream. Waiting for the expected count rather than for the publisher lets
# the run stop as soon as the submission set is complete, while the drain-aware
# stall check still distinguishes a worker that is behind from one that is stuck.
t=0
stall=0
last=0
while [[ "$t" -lt "$REPLAY_TIMEOUT" ]]; do
  saved=$(find "$RUN_DIR/dense" -name '*.png' 2>/dev/null | wc -l)
  [[ "$saved" -ge "$EXPECTED" ]] && break
  if [[ "$saved" -ne "$last" ]]; then
    stall=0
  elif ! kill -0 "$PUB_PID" 2>/dev/null; then
    stall=$((stall + 2))
    [[ "$stall" -ge "$STALL_LIMIT_S" ]] && break
  fi
  last=$saved
  sleep 2
  t=$((t + 2))
done
sleep 4
dense=$(find "$RUN_DIR/dense" -name '*.png' 2>/dev/null | wc -l)
echo ">>> saved dense=$dense/$EXPECTED after ~${t}s"
cleanup
trap - EXIT

# An incomplete set cannot be submitted: the server requires exactly as many
# files as the schedule has rows, so flag it rather than let packaging proceed.
rm -f "$RUN_DIR/incomplete.flag"
if [[ "$dense" -lt "$EXPECTED" ]]; then
  printf 'dense=%s expected=%s\n' "$dense" "$EXPECTED" > "$RUN_DIR/incomplete.flag"
  echo ">>> WARNING: incomplete prediction set, flagged"
fi

# The exported names must be exactly the schedule's file indices, zero padded to
# six digits. A mismatch means the node numbered the exports itself, which would
# silently misalign every frame at evaluation time.
python3 - "$SCHEDULE" "$RUN_DIR" <<'PY'
import sys
from pathlib import Path

schedule, run_dir = Path(sys.argv[1]), Path(sys.argv[2])
want = set()
for line in schedule.read_text(encoding='utf-8').splitlines():
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    want.add(int(line.replace(',', ' ').split()[2]))
have = {int(p.stem) for p in (run_dir / 'dense').glob('*.png') if p.stem.isdigit()}
missing, extra = sorted(want - have), sorted(have - want)
flag = run_dir / 'misnamed.flag'
flag.unlink(missing_ok=True)
if missing or extra:
    flag.write_text(f'missing={missing[:20]}\nextra={extra[:20]}\n', encoding='utf-8')
    print(f'>>> WARNING: {len(missing)} missing and {len(extra)} unexpected indices')
else:
    print(f'>>> index check OK ({len(have)} files match the schedule)')
PY

echo ">>> DONE $SEQUENCE"
