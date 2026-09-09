#!/usr/bin/env python3
"""
Generate MomentFlow parameter files for the DSEC-Flow test-split submission.

Every sequence gets the same configuration, imported from the ablation study's
``REFERENCE`` dict so that the submission cannot silently diverge from the
configuration the paper reports. The benchmark's submission policy requires one
parameter set for the whole test set, so the only per-sequence values are the
output directory, the timing log path and the official evaluation schedule.

Alexandru Cretu <alexandru.cretu@uniroma2.it>

August 26, 2026
"""

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

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'momentflow_ablation'))

from variants import REFERENCE, WS, render_yaml  # noqa: E402  (needs the path insert)

# The seven sequences of the DSEC-Flow test split, as listed in
# test_forward_optical_flow_timestamps.zip. A submission must contain exactly
# these directories.
TEST_SEQUENCES = [
    'interlaken_00_b',
    'interlaken_01_a',
    'thun_01_a',
    'thun_01_b',
    'zurich_city_12_a',
    'zurich_city_14_c',
    'zurich_city_15_a',
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--repo-root', type=Path, default=Path(__file__).resolve().parents[2],
        help='Host-side workspace root, used only to place generated files.')
    parser.add_argument('--sequence', action='append', default=[])
    args = parser.parse_args()

    sequences = args.sequence or TEST_SEQUENCES
    unknown = [s for s in sequences if s not in TEST_SEQUENCES]
    if unknown:
        parser.error(f'not DSEC-Flow test sequences: {unknown}')

    written = 0
    for seq in sequences:
        schedule = args.repo_root / 'logs' / 'dsec' / seq / 'test_forward_flow' / f'{seq}.csv'
        if not schedule.is_file():
            print(f'!! missing schedule for {seq}: {schedule}')
            continue
        rows = sum(
            1 for line in schedule.read_text(encoding='utf-8').splitlines()
            if line.strip() and not line.strip().startswith('#'))

        run_dir = f'{WS}/logs/dsec_test/{seq}'
        params = dict(REFERENCE)
        params['save_output_dir'] = run_dir
        params['timing_log_path'] = f'{run_dir}/timing_ms.csv'
        # The official CSV is already the three-column (from, to, index) form the
        # node parses, so it is used verbatim: no derived schedule can drift from
        # the indices the evaluation server expects.
        params['save_timestamp_file'] = (
            f'{WS}/logs/dsec/{seq}/test_forward_flow/{seq}.csv')
        # Inert when the schedule carries indices, which it does; kept explicit so
        # a malformed schedule fails loudly rather than inventing a numbering.
        params['save_first_index'] = 0
        params['save_index_step'] = 1

        target = args.repo_root / 'logs' / 'dsec_test' / seq
        target.mkdir(parents=True, exist_ok=True)
        (target / 'config.yaml').write_text(render_yaml(params), encoding='utf-8')
        (target / 'expected.txt').write_text(f'{rows}\n', encoding='utf-8')
        written += 1
        print(f'{seq:20s} {rows:4d} intervals -> {target}/config.yaml')

    print(f'Wrote {written} test configs')
    return 0 if written == len(sequences) else 1


if __name__ == '__main__':
    raise SystemExit(main())
