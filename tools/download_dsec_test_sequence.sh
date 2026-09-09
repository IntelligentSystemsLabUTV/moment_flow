#!/usr/bin/env bash
# Download the left event stream of one DSEC-Flow *test* sequence.
#
# The test split has no public optical-flow ground truth, so this script fetches
# only events_left and installs the official forward-flow evaluation schedule
# from test_forward_optical_flow_timestamps.zip. The resulting layout matches the
# training layout, so the replay and export tooling needs no special case:
#
#   logs/dsec/<sequence>/events_left/events.h5
#   logs/dsec/<sequence>/events_left/rectify_map.h5
#   logs/dsec/<sequence>/test_forward_flow/<sequence>.csv
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

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bin/download_dsec_test_sequence.sh <sequence>...
  bin/download_dsec_test_sequence.sh --all

Downloads events_left for one or more DSEC-Flow test sequences and installs the
official evaluation schedule. The seven benchmark test sequences are:

  interlaken_00_b interlaken_01_a thun_01_a thun_01_b
  zurich_city_12_a zurich_city_14_c zurich_city_15_a

Environment:
  DSEC_ROOT       Output root. Default: <workspace>/logs/dsec
  DSEC_KEEP_ZIPS  Set to 1 to keep downloaded zip files. Default: 0
  WGET_ARGS       Extra arguments passed to wget.
EOF
}

TEST_SEQUENCES=(interlaken_00_b interlaken_01_a thun_01_a thun_01_b
                zurich_city_12_a zurich_city_14_c zurich_city_15_a)

[[ $# -eq 0 ]] && { usage; exit 1; }
case "${1:-}" in
  -h | --help ) usage; exit 0 ;;
  --all ) sequences=("${TEST_SEQUENCES[@]}") ;;
  * ) sequences=("$@") ;;
esac

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace="$(cd "$script_dir/.." && pwd)"
dsec_root="${DSEC_ROOT:-$workspace/logs/dsec}"
download_page="https://dsec.ifi.uzh.ch/dsec-datasets/download/"
schedule_url="https://download.ifi.uzh.ch/rpg/DSEC/test_forward_optical_flow_timestamps.zip"
keep_zips="${DSEC_KEEP_ZIPS:-0}"

for cmd in wget unzip find grep sed; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "error: missing command: $cmd" >&2; exit 1; }
done

for seq in "${sequences[@]}"; do
  case "$seq" in
    *[!A-Za-z0-9_]* | "" ) echo "error: invalid sequence name '$seq'" >&2; exit 1 ;;
  esac
  found=0
  for known in "${TEST_SEQUENCES[@]}"; do
    [[ "$seq" == "$known" ]] && found=1
  done
  # Refuse a sequence that is not on the benchmark list: the submission must
  # contain exactly the seven, and a stray directory fails the format check.
  if [[ "$found" -ne 1 ]]; then
    echo "error: '$seq' is not a DSEC-Flow test sequence" >&2
    echo "       expected one of: ${TEST_SEQUENCES[*]}" >&2
    exit 1
  fi
done

wget_extra=()
[[ -n "${WGET_ARGS:-}" ]] && read -r -a wget_extra <<< "$WGET_ARGS"

staging="$dsec_root/.test_downloads"
mkdir -p "$staging"

echo "Fetching DSEC download page..."
page_html="$staging/download.html"
wget -q "${wget_extra[@]}" -O "$page_html" "$download_page"

# The evaluation schedule is one small archive covering all seven sequences, so
# fetch it once rather than per sequence.
schedule_zip="$staging/test_forward_optical_flow_timestamps.zip"
schedule_dir="$staging/schedules"
if [[ ! -d "$schedule_dir" ]]; then
  echo "Downloading evaluation schedule"
  wget -q -c "${wget_extra[@]}" -O "$schedule_zip" "$schedule_url"
  mkdir -p "$schedule_dir"
  unzip -q -o "$schedule_zip" -d "$schedule_dir"
fi

for seq in "${sequences[@]}"; do
  echo "==== $seq"
  target="$dsec_root/$seq"
  events_dir="$target/events_left"
  sched_dir="$target/test_forward_flow"
  mkdir -p "$events_dir" "$sched_dir"

  csv_src="$(find "$schedule_dir" -type f -name "${seq}.csv" | head -n 1)"
  [[ -n "$csv_src" ]] || { echo "error: no schedule for $seq" >&2; exit 1; }
  cp -f "$csv_src" "$sched_dir/${seq}.csv"
  rows="$(grep -cvE '^\s*(#|$)' "$sched_dir/${seq}.csv")"

  if [[ -s "$events_dir/events.h5" && -s "$events_dir/rectify_map.h5" ]]; then
    echo "  events already present, skipping download"
    echo "  schedule: $rows intervals"
    continue
  fi

  url="$(grep -Eo 'https://download\.ifi\.uzh\.ch/[^"]+' "$page_html" \
    | sed 's/&amp;/\&/g' | grep -E "/${seq}/${seq}_events_left\.zip$" | head -n 1 || true)"
  [[ -n "$url" ]] || { echo "error: no events_left.zip link for $seq" >&2; exit 1; }

  zip_path="$staging/${seq}_events_left.zip"
  if [[ -s "$zip_path" ]] && unzip -tq "$zip_path" >/dev/null 2>&1; then
    echo "  using existing zip"
  else
    echo "  downloading events_left.zip"
    wget -q -c "${wget_extra[@]}" -O "$zip_path" "$url"
  fi

  tmp="$staging/.extract_$seq"
  rm -rf "$tmp"; mkdir -p "$tmp"
  echo "  extracting"
  unzip -q -o "$zip_path" -d "$tmp"
  for name in events.h5 rectify_map.h5; do
    src="$(find "$tmp" -type f -name "$name" | head -n 1)"
    [[ -n "$src" ]] || { echo "error: $name missing after extracting $seq" >&2; exit 1; }
    mv -f "$src" "$events_dir/$name"
  done
  rm -rf "$tmp"
  # Reclaim as we go: the seven archives are 10 GiB together, and keeping them
  # alongside the extracted streams doubles the footprint for no benefit.
  [[ "$keep_zips" == "1" ]] || rm -f "$zip_path"
  echo "  done: $(du -h "$events_dir/events.h5" | cut -f1) events, $rows intervals"
done

echo
echo "All requested test sequences ready under $dsec_root"
