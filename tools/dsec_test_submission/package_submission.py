#!/usr/bin/env python3
"""
Verify and package a DSEC-Flow test-split submission.

Checks the prediction set against the official submission format before zipping,
because the evaluation server accepts a structurally valid archive and then
reports a score: a silent numbering or channel-order mistake would come back as
a bad result rather than as an error.

Checked, per https://dsec.ifi.uzh.ch/optical-flow-submission-format/:
  - exactly the seven test sequences, one directory each;
  - one PNG per row of that sequence's official schedule;
  - file names are the schedule's file indices, zero padded to six digits;
  - each PNG is 3-channel 16-bit, with the third channel restricted to 0 or 1.

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
import struct
import sys
import zipfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_configs import TEST_SEQUENCES  # noqa: E402  (needs the path insert)


def read_png_header(path: Path) -> tuple[int, int, int, int]:
    """Return (width, height, bit_depth, colour_type) from a PNG IHDR.

    Read directly rather than through an image library: the packaging step must
    run with nothing beyond the standard library, and only the header is needed.
    """
    with path.open('rb') as fh:
        signature = fh.read(8)
        if signature != b'\x89PNG\r\n\x1a\n':
            raise ValueError(f'{path} is not a PNG')
        length = struct.unpack('>I', fh.read(4))[0]
        if fh.read(4) != b'IHDR' or length != 13:
            raise ValueError(f'{path} has no IHDR')
        width, height, depth, colour = struct.unpack('>IIBB', fh.read(10))
    return width, height, depth, colour


def schedule_indices(repo_root: Path, seq: str) -> list[int]:
    path = repo_root / 'logs' / 'dsec' / seq / 'test_forward_flow' / f'{seq}.csv'
    out = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            out.append(int(line.replace(',', ' ').split()[2]))
    return out


def check_third_channel(path: Path) -> set[int]:
    """Decode a 16-bit RGB PNG far enough to collect its third-channel values."""
    raw = bytearray()
    width = height = None
    with path.open('rb') as fh:
        fh.read(8)
        while True:
            head = fh.read(8)
            if len(head) < 8:
                break
            length, kind = struct.unpack('>I', head[:4])[0], head[4:]
            data = fh.read(length)
            fh.read(4)
            if kind == b'IHDR':
                width, height = struct.unpack('>II', data[:8])
            elif kind == b'IDAT':
                raw += data
            elif kind == b'IEND':
                break
    pixels = zlib.decompress(bytes(raw))
    stride = width * 6                      # 3 channels, 2 bytes each
    values = set()
    prior = bytearray(stride)
    pos = 0
    for _ in range(height):
        filter_type = pixels[pos]
        line = bytearray(pixels[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        # Undo the per-scanline filter; only these two appear in practice, and an
        # unexpected one is reported rather than silently mis-decoded.
        if filter_type == 0:
            pass
        elif filter_type == 1:
            for i in range(6, stride):
                line[i] = (line[i] + line[i - 6]) & 0xFF
        elif filter_type == 2:
            for i in range(stride):
                line[i] = (line[i] + prior[i]) & 0xFF
        else:
            raise ValueError(f'{path}: unsupported PNG filter {filter_type}')
        for i in range(4, stride, 6):
            values.add((line[i] << 8) | line[i + 1])
        prior = line
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path,
                        default=Path(__file__).resolve().parents[2])
    parser.add_argument('--out', type=Path, default=None,
                        help='Output zip. Default: logs/dsec_test/momentflow_submission.zip')
    parser.add_argument('--deep', action='store_true',
                        help='Decode one PNG per sequence to verify the third channel.')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()

    root = args.repo_root / 'logs' / 'dsec_test'
    out = args.out or root / 'momentflow_submission.zip'
    problems = []
    payload = []

    for seq in TEST_SEQUENCES:
        want = schedule_indices(args.repo_root, seq)
        dense = root / seq / 'dense'
        if not dense.is_dir():
            problems.append(f'{seq}: no predictions at {dense}')
            continue
        for flag in ('incomplete.flag', 'misnamed.flag'):
            if (root / seq / flag).is_file():
                problems.append(f'{seq}: {flag} present -- '
                                f'{(root / seq / flag).read_text().strip()}')
        have = {int(p.stem): p for p in dense.glob('*.png') if p.stem.isdigit()}
        missing = sorted(set(want) - set(have))
        extra = sorted(set(have) - set(want))
        if missing:
            problems.append(f'{seq}: {len(missing)} missing indices, first {missing[:5]}')
        if extra:
            problems.append(f'{seq}: {len(extra)} unexpected indices, first {extra[:5]}')

        for idx in want:
            path = have.get(idx)
            if path is None:
                continue
            name = f'{idx:06d}.png'
            if path.name != name:
                problems.append(f'{seq}: {path.name} should be {name}')
            payload.append((f'{seq}/{name}', path))

        sample = have.get(want[0]) if want else None
        if sample is not None:
            width, height, depth, colour = read_png_header(sample)
            if (width, height) != (640, 480):
                problems.append(f'{seq}: {sample.name} is {width}x{height}, expected 640x480')
            if depth != 16:
                problems.append(f'{seq}: {sample.name} is {depth}-bit, expected 16')
            if colour != 2:
                problems.append(f'{seq}: {sample.name} colour type {colour}, expected 2 (RGB)')
            if args.deep:
                values = check_third_channel(sample)
                if not values <= {0, 1}:
                    problems.append(
                        f'{seq}: {sample.name} third channel holds {sorted(values)[:5]}, '
                        f'expected only 0 or 1')

        print(f'{seq:20s} {len(have):4d}/{len(want):<4d} files')

    if problems:
        print('\nFAILED verification:')
        for p in problems:
            print(f'  - {p}')
        return 1
    print(f'\nverification passed: {len(payload)} files across {len(TEST_SEQUENCES)} sequences')

    if args.verify_only:
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    # Stored rather than deflated: the payload is already-compressed PNG data, so
    # deflate costs minutes and saves almost nothing.
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_STORED) as zf:
        for arcname, path in payload:
            zf.write(path, arcname)

    # Re-open and validate what was actually written. A truncated or partially
    # flushed archive is still a readable zip, so the only way to know the
    # submission is complete is to read it back.
    import re
    want = {a for a, _ in payload}
    with zipfile.ZipFile(out) as zf:
        got = set(zf.namelist())
        broken = zf.testzip()
    problems = []
    if broken is not None:
        problems.append(f'corrupt entry: {broken}')
    if got != want:
        problems.append(f'{len(want - got)} missing and {len(got - want)} unexpected entries')
    pattern = re.compile(r'^[a-z_0-9]+/\d{6}\.png$')
    bad = sorted(n for n in got if not pattern.match(n))
    if bad:
        problems.append(f'entries not matching <sequence>/<6 digits>.png: {bad[:5]}')
    dirs = sorted({n.split('/')[0] for n in got})
    if dirs != sorted(TEST_SEQUENCES):
        problems.append(f'top-level directories are {dirs}')
    if problems:
        print('\nARCHIVE CHECK FAILED:')
        for p_ in problems:
            print(f'  - {p_}')
        return 1
    print(f'wrote {out} ({out.stat().st_size / 2**20:.1f} MiB)')
    print(f'archive check passed: {len(got)} entries, {len(dirs)} sequence directories')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
