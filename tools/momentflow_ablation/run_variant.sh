#!/usr/bin/env bash
# Run one MomentFlow ablation variant end to end, inside the DUA container.
#
# Replays one DSEC sequence through moment_flow with the variant's own
# parameter file, waits until every scheduled prediction is on disk, then scores
# the dense and event-supported exports against the DSEC ground truth.
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
VARIANT=${1:?usage: run_variant.sh VARIANT [SEQUENCE]}
SEQUENCE=${2:-thun_00_a}
SUBSAMPLE=${SUBSAMPLE:-}
REALTIME_FACTOR=${REALTIME_FACTOR:-1.0}
SETTLE_S=${SETTLE_S:-12}
REPLAY_TIMEOUT=${REPLAY_TIMEOUT:-1200}

RUN_DIR="$WS/logs/ablation/$SEQUENCE/$VARIANT"
GT_DIR="$WS/logs/dsec/$SEQUENCE/optical_flow_forward"
GT_SCHEDULE="$GT_DIR/${SEQUENCE}_optical_flow_forward_timestamps.txt"
H5="$WS/logs/dsec/$SEQUENCE/events_left/events.h5"
CONFIG="$RUN_DIR/config.yaml"

[[ -f "$CONFIG" ]] || { echo "FATAL: missing $CONFIG (run variants.py first)"; exit 1; }
[[ -f "$GT_SCHEDULE" ]] || { echo "FATAL: missing $GT_SCHEDULE"; exit 1; }
[[ -f "$H5" ]] || { echo "FATAL: missing $H5"; exit 1; }

mkdir -p "$RUN_DIR"

# The schedule subsampling factor travels with the variant, so a single run and
# a batch run cannot disagree about it.
if [[ -z "$SUBSAMPLE" ]]; then
  SUBSAMPLE=$(cat "$RUN_DIR/subsample.txt" 2>/dev/null || echo 1)
fi

# Always build an explicit three-column schedule. The two-column DSEC training
# timestamp file carries no indices, so the node would infer them as
# first + k*step -- but the ground-truth indices are NOT a uniform arithmetic
# sequence on 10 of the 18 sequences (zurich_city_10_a runs 2..2312 for 752
# files), so the inference silently misaligns predictions with ground truth and
# the name-matched benchmark then scores a partial, shifted subset.
python3 - "$GT_SCHEDULE" "$GT_DIR" "$RUN_DIR/schedule.txt" "$SUBSAMPLE" <<'PY'
import glob
import re
import sys

src, gt_dir, dst = sys.argv[1], sys.argv[2], sys.argv[3]
step = max(1, int(sys.argv[4]))

# Pair each timestamp row with the real ground-truth file index. The indices must
# come from the ground-truth filenames, not from a 2,4,6,... assumption: the flow
# ground truth starts at 134 for zurich_city_01_a and 874 for zurich_city_07_a,
# and a subsampled schedule built on the wrong indices scores no frames at all.
indices = sorted(
    int(m.group(1)) for p in glob.glob(f'{gt_dir}/*.png')
    if (m := re.search(r'(\d+)\.png$', p)))
rows = []
for line in open(src):
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    from_us, to_us = (int(v) for v in line.replace(',', ' ').split()[:2])
    rows.append((from_us, to_us))
if len(rows) != len(indices):
    raise SystemExit(
        f'schedule/ground-truth mismatch: {len(rows)} timestamp rows, {len(indices)} PNGs')
with open(dst, 'w') as fh:
    fh.write('# from_timestamp_us, to_timestamp_us, file_index\n')
    for (from_us, to_us), idx in list(zip(rows, indices))[::step]:
        fh.write(f'{from_us}, {to_us}, {idx}\n')
PY
EXPECTED=$(grep -cvE '^\s*(#|$)' "$RUN_DIR/schedule.txt")
echo ">>> variant=$VARIANT sequence=$SEQUENCE expected=$EXPECTED rf=$REALTIME_FACTOR"

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

# Stop as soon as every scheduled prediction is written, since the ground truth
# often covers only part of the sequence.
#
# The publisher exiting does NOT mean the run is over. Raw-flow saving keeps every
# queued chunk on purpose, so on a dense sequence the worker falls behind the
# real-time replay and still has a long backlog to drain after the last event has
# been published. Tearing down at that moment silently truncates the prediction
# set, and the benchmark then scores whatever partial set it finds. So give up
# only once the publisher is gone AND no new prediction has appeared for
# STALL_LIMIT_S, which is what actually distinguishes "draining" from "stuck".
t=0
stall=0
last=0
STALL_LIMIT_S=${STALL_LIMIT_S:-40}
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
sparse=$(find "$RUN_DIR/sparse" -name '*.png' 2>/dev/null | wc -l)
echo ">>> saved dense=$dense/$EXPECTED sparse=$sparse after ~${t}s"
cleanup
trap - EXIT

# An incomplete export is a broken run, not a smaller one: --allow-missing means
# the scorer would otherwise report a plausible number over a subset of frames.
rm -f "$RUN_DIR/incomplete.flag"
if [[ "$dense" -lt "$EXPECTED" ]]; then
  printf 'dense=%s expected=%s sparse=%s\n' "$dense" "$EXPECTED" "$sparse" \
    > "$RUN_DIR/incomplete.flag"
  echo ">>> WARNING: incomplete export, flagged for exclusion"
fi

cd "$WS"
# Score the dense and event-supported exports concurrently. The benchmark is
# single-threaded Python over one PNG pair at a time and dominates wall time on
# long sequences, while the replay it follows has already released the CPUs.
declare -A score_pid=()
for mode in dense sparse; do
  [[ "$mode" == dense ]] && mask=gt || mask=intersection
  # Match on the estimation interval, not on the filename. The node records the
  # (from_us, to_us) of every export in moment_flow_timestamps.txt, so a
  # prediction is paired with the ground-truth interval it was actually solved
  # over. Filename-based matching required the node to reproduce the ground-truth
  # index scheme, which is not a uniform arithmetic sequence on 10 of the 18
  # sequences and silently mispaired or dropped frames when the inference was
  # wrong. The 1 ms tolerance turns any residual misalignment into a missing
  # match rather than a wrong pairing.
  python3 -m tools.dsec_flow_benchmark \
    --gt-dir "$GT_DIR" --pred-dir "$RUN_DIR/$mode" --mask-mode "$mask" \
    --match timestamp --pred-timestamps "$RUN_DIR/moment_flow_timestamps.txt" \
    --timestamp-key from --timestamp-tolerance-us 1000 --allow-missing \
    --output-json "$RUN_DIR/${mode}_benchmark.json" \
    --output-csv "$RUN_DIR/${mode}_frames.csv" \
    > "$RUN_DIR/${mode}_benchmark.txt" 2>&1 &
  score_pid[$mode]=$!
done
for mode in dense sparse; do
  wait "${score_pid[$mode]}" || echo ">>> WARNING: $mode scoring failed"
  echo ">>> $mode:"
  sed 's/^/    /' "$RUN_DIR/${mode}_benchmark.txt"
done

rm -f "$RUN_DIR/misaligned.flag"
scored=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['summary'].get('frames',0))" \
  "$RUN_DIR/dense_benchmark.json" 2>/dev/null || echo 0)
if [[ "$scored" -lt "$dense" ]]; then
  printf 'scored=%s exported=%s\n' "$scored" "$dense" > "$RUN_DIR/misaligned.flag"
  echo ">>> WARNING: only $scored of $dense exports matched a ground-truth interval"
fi

printf '%s\t%s\t%s\n' "$VARIANT" "$dense" "$EXPECTED" >> "$WS/logs/ablation/$SEQUENCE/completed.tsv"

# A full sweep writes far more prediction PNGs than the machine has room for
# (~0.5 MiB each, ~8 GiB per pass over the whole train split). The benchmark JSON
# and the per-frame CSV keep everything the report needs, so the PNGs are only
# worth keeping while a run is being inspected by hand.
# Purge by default: a full pass writes ~8 GiB of PNGs and a forgotten opt-in
# filled the disk once already. Note that an environment variable set on the host
# does not reach the container through dua exec, so an opt-out that has to be
# remembered is the wrong default. Set KEEP_PREDICTIONS=1 inside the container
# command when the images themselves are needed, e.g. for correlation statistics.
if [[ -z "${KEEP_PREDICTIONS:-}" ]]; then
  freed=$(du -sm "$RUN_DIR/dense" "$RUN_DIR/sparse" 2>/dev/null | awk '{s+=$1} END {print s+0}')
  rm -rf "$RUN_DIR/dense" "$RUN_DIR/sparse"
  echo ">>> purged predictions (${freed} MiB)"
fi

echo ">>> DONE $VARIANT"
