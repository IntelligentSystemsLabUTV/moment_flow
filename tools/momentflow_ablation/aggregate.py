#!/usr/bin/env python3
"""
Aggregate MomentFlow ablation runs into a results table.

Pools each variant over a sequence set and, crucially, also reports the
per-sequence delta. A pooled number alone would hide an axis that helps easy
scenes and hurts hard ones, which is the whole reason for running on more than
one sequence: the largest sequence of the train split carries more valid pixels
than ten of the smallest together.

Alexandru Cretu <alexandru.cretu@uniroma2.it>

August 24, 2026
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
import csv
import json
import random
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from variants import SEQUENCE_SETS, VARIANTS  # noqa: E402  (needs the path insert)

METRIC_KEYS = ('epe', 'ae', '1pe_pct', '2pe_pct', '3pe_pct')

# Deltas below this are treated as run-to-run noise rather than effects, both for
# sign-flip detection and for the summary verdicts.
#
# Calibrated, not guessed. The s_ref control re-runs the reference configuration
# in a later session: over the five S4 sequences the per-sequence EPE difference
# on a configuration that did not change spans -0.076 to +0.015 px, stdev 0.037,
# and pools to -0.016 px. So 0.08 px is the smallest per-sequence delta that the
# replay can actually resolve; the previous 0.02 px promoted pure delivery jitter
# to an effect and produced spurious sign flips. The noise grows with sequence
# difficulty (the largest is on zurich_city_02_c, the hardest), so a single
# global bound is conservative on the easy sequences and about right on the hard
# ones.
NOISE_PX = 0.08

# Relative event-count difference above which a run is reported as not comparable
# with the baseline. Also calibrated against the s_ref control: two runs of the
# same configuration differ by up to 0.161% because event delivery is
# load dependent, so the previous 0.1% bound fired on configuration-identical
# runs. 0.5% sits above that null and far below the two legitimate stream
# changes in the campaign (gap filling off, +3.4%; the 2 Hz schedule, -31.5%).
STREAM_TOL = 0.005


def pixel_weighted(frames: list[dict]) -> dict:
    """Pixel-weighted aggregate over an arbitrary set of frames.

    Each frame's metric is already the mean over that frame's valid pixels, so
    weighting by valid_pixels reproduces the pooled per-pixel mean exactly.
    """
    total = sum(int(f['valid_pixels']) for f in frames)
    out = {'valid_pixels': total, 'frames': len(frames)}
    if total == 0:
        return out | {k: float('nan') for k in METRIC_KEYS}
    for key in METRIC_KEYS:
        out[key] = sum(float(f[key]) * int(f['valid_pixels']) for f in frames) / total
    return out


def paired_delta(variant_frames: dict, ref_frames: dict, resamples: int = 2000) -> dict:
    """Paired per-frame EPE delta with a bootstrap interval, keyed by (sequence, frame).

    The delta is pixel weighted, matching how DSEC-Flow pools its metrics and how
    the EPE columns of this table are computed. An unweighted mean of per-frame
    deltas is a different estimand: frames carry between 20 k and 80 k valid
    pixels depending on the sequence, so the two disagree by more than the
    interval width, and an interval that excludes its own point estimate is not
    reportable. The frames are the resampling unit, since that is the level at
    which the runs are paired; pixels within a frame are not independent.
    """
    common = sorted(set(variant_frames) & set(ref_frames))
    pairs = [(float(variant_frames[k]['epe']) - float(ref_frames[k]['epe']),
              int(ref_frames[k]['valid_pixels'])) for k in common]
    if len(pairs) < 2:
        return {'n': len(pairs), 'mean': float('nan'),
                'lo': float('nan'), 'hi': float('nan'), 'worse': 0}

    def weighted(sample):
        w = sum(x[1] for x in sample)
        return sum(d * px for d, px in sample) / w if w else float('nan')

    rng = random.Random(0)
    means = sorted(weighted(rng.choices(pairs, k=len(pairs))) for _ in range(resamples))
    return {
        'n': len(pairs),
        'mean': weighted(pairs),
        'lo': means[int(0.025 * resamples)],
        'hi': means[int(0.975 * resamples)],
        'worse': sum(1 for d, _ in pairs if d > 0),
    }


def load_run(root: Path, seq: str, variant: str) -> dict | None:
    """Load one (variant, sequence) run, or None when it has not been scored."""
    run = root / 'logs' / 'ablation' / seq / variant
    dense_path = run / 'dense_benchmark.json'
    if not dense_path.is_file():
        return None
    # A run whose export was cut short, or whose exports did not line up with the
    # ground-truth intervals, is excluded outright. Scoring either would produce a
    # believable EPE over an arbitrary subset, which is worse than no data point.
    for flag in (run / 'incomplete.flag', run / 'misaligned.flag'):
        if flag.is_file():
            print(f'!! excluding {variant}/{seq}: {flag.name} '
                  f'{flag.read_text(encoding="utf-8").strip()}')
            return None
    try:
        dense = json.loads(dense_path.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return None
    sparse = None
    sparse_path = run / 'sparse_benchmark.json'
    if sparse_path.is_file():
        try:
            sparse = json.loads(sparse_path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            sparse = None
    return {
        'summary': dense['summary'],
        'frames': dense['frames'],
        'sparse': sparse['summary'] if sparse else {},
        'timing': load_timing(run / 'timing_ms.csv', dense['summary'].get('frames')),
    }


def load_timing(path: Path, limit: int | None = None) -> dict:
    """Summarize per-window timing, keeping only the scheduled windows.

    The node keeps profiling after the export schedule is exhausted, on windows
    that were never scored; those rows come last, so truncating to the number of
    scored frames aligns timing with accuracy.
    """
    if not path.is_file():
        return {}
    with path.open(encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    if limit is not None:
        rows = rows[:limit]
    if not rows:
        return {}

    def col(name):
        return [float(r[name]) for r in rows if r.get(name) not in (None, '')]

    return {'rows': rows, 'total': col('total_ms'), 'solve': col('solve_moments_ms'),
            'refine': col('refine_sub_ms'), 'events': col('num_events')}


def pct(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int(p * len(values)))]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--set', choices=sorted(SEQUENCE_SETS))
    parser.add_argument('--sequence', action='append', default=[])
    parser.add_argument('--repo-root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--label', help='Output basename. Defaults to the set or sequence name.')
    parser.add_argument(
        '--baseline', default='reference',
        help='Variant every delta and paired CI is measured against. A sweep that '
             'carries its own control run should name it here: comparing against a '
             'reference scored in an earlier session folds run-to-run event-delivery '
             'noise into the parameter effect.')
    args = parser.parse_args()

    if args.set:
        sequences, label = SEQUENCE_SETS[args.set], args.label or args.set
    elif args.sequence:
        sequences = args.sequence
        label = args.label or ('_'.join(args.sequence) if len(args.sequence) < 3 else 'custom')
    else:
        parser.error('pass --set or --sequence')

    meta = {name: (tier, axis, desc, ov) for name, tier, axis, desc, ov in VARIANTS}

    # Collect every (variant, sequence) run that has been scored.
    runs: dict[str, dict[str, dict]] = {}
    for name in meta:
        per_seq = {}
        for seq in sequences:
            run = load_run(args.repo_root, seq, name)
            if run is not None:
                per_seq[seq] = run
        if per_seq:
            runs[name] = per_seq

    if args.baseline not in runs:
        print(f'!! no scored {args.baseline} run; deltas unavailable')
        return 1
    ref = runs[args.baseline]
    ref_seqs = set(ref)

    def keyed_frames(per_seq: dict) -> dict:
        return {(s, f['frame']): f for s, r in per_seq.items() for f in r['frames']}

    ref_keyed = keyed_frames(ref)
    ref_pooled = pixel_weighted(list(ref_keyed.values()))
    ref_per_seq_epe = {s: pixel_weighted(r['frames'])['epe'] for s, r in ref.items()}

    # Event-stream integrity. Replay loses events when the consumer falls behind,
    # and the loss is load-dependent, so two runs of the same configuration can
    # process slightly different streams and differ by ~0.1 px on the hardest
    # sequence. Variants that touch neither the solve-event cap nor the window
    # length must see an identical stream, so any deviation from the reference
    # means the run is not comparable. Only detectable, not preventable here:
    # the reader-side QoS lives in the node.
    STREAM_KEYS = {'max_solve_events', 'max_window_ms'}
    ref_events = {}
    for s, r in ref.items():
        ev = r['timing'].get('events')
        if ev:
            ref_events[s] = st.mean(ev)

    rows = []
    for name, per_seq in runs.items():
        tier, axis, desc, ov = meta[name]
        # Compare only on sequences both the variant and the reference have, so a
        # partially finished sweep still produces honest deltas.
        shared = sorted(set(per_seq) & ref_seqs)
        if not shared:
            continue
        var_keyed = {k: v for k, v in keyed_frames(per_seq).items() if k[0] in shared}
        ref_shared = {k: v for k, v in ref_keyed.items() if k[0] in shared}
        pooled = pixel_weighted(list(var_keyed.values()))
        base = pixel_weighted(list(ref_shared.values()))
        paired = paired_delta(var_keyed, ref_shared)

        per_seq_delta = {
            s: pixel_weighted(per_seq[s]['frames'])['epe'] - ref_per_seq_epe[s] for s in shared}
        effects = [d for d in per_seq_delta.values() if abs(d) > NOISE_PX]
        sign_flip = bool(effects) and not (
            all(d > 0 for d in effects) or all(d < 0 for d in effects))

        timing = {}
        for s in shared:
            for k, v in per_seq[s]['timing'].items():
                if k != 'rows':
                    timing.setdefault(k, []).extend(v)

        # Flag a run whose event stream does not match the reference's, unless the
        # variant deliberately changes how many events reach the solver.
        stream_ok = True
        if not (set(ov) & STREAM_KEYS):
            for s in shared:
                ev = per_seq[s]['timing'].get('events')
                if ev and s in ref_events and ref_events[s] > 0:
                    if abs(st.mean(ev) - ref_events[s]) / ref_events[s] > STREAM_TOL:
                        stream_ok = False
                        print(f'!! {name}/{s}: event stream differs from reference by '
                              f'{100 * (st.mean(ev) - ref_events[s]) / ref_events[s]:+.2f}% '
                              f'-- run not comparable')

        rows.append({
            'variant': name, 'tier': tier, 'axis': axis, 'description': desc,
            'overrides': ';'.join(f'{k}={v}' for k, v in sorted(ov.items())),
            'sequences': len(shared), 'frames': pooled['frames'],
            'valid_pixels': pooled['valid_pixels'],
            'epe': pooled['epe'], 'epe_delta': pooled['epe'] - base['epe'],
            'paired_delta': paired['mean'], 'paired_ci_lo': paired['lo'],
            'paired_ci_hi': paired['hi'], 'frames_worse': paired['worse'],
            'sign_flip': int(sign_flip),
            'stream_ok': int(stream_ok),
            'worst_seq_delta': max(per_seq_delta.values(), key=abs) if per_seq_delta else 0.0,
            'ae': pooled['ae'], '1pe_pct': pooled['1pe_pct'],
            '2pe_pct': pooled['2pe_pct'], '3pe_pct': pooled['3pe_pct'],
            'sparse_epe': st.mean([r['sparse']['epe'] for r in per_seq.values()
                                   if r['sparse']]) if any(
                r['sparse'] for r in per_seq.values()) else '',
            'solve_med_ms': st.median(timing['solve']) if timing.get('solve') else '',
            'solve_p95_ms': pct(timing['solve'], 0.95) if timing.get('solve') else '',
            'total_med_ms': st.median(timing['total']) if timing.get('total') else '',
            'total_p95_ms': pct(timing['total'], 0.95) if timing.get('total') else '',
            'events_mean': int(st.mean(timing['events'])) if timing.get('events') else '',
            **{f'd_{s}': per_seq_delta[s] for s in shared},
        })

    out_dir = args.repo_root / 'logs' / 'ablation'
    fields = list(dict.fromkeys(k for r in rows for k in r))
    csv_path = out_dir / f'{label}_results.csv'
    with csv_path.open('w', encoding='utf-8', newline='') as handle:
        w = csv.DictWriter(handle, fieldnames=fields)
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r['variant'] != args.baseline, r['tier'], r['epe'])):
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})

    # Markdown, grouped by tier then axis, with the reference repeated for context.
    by_name = {r['variant']: r for r in rows}
    reference = by_name[args.baseline]
    lines = [f'# Ablation results: {label} ({len(sequences)} sequences, '
             f"{reference['frames']} frames, {reference['valid_pixels'] / 1e6:.1f} Mpx)", '']
    header = ('| Variant | Change | EPE | ΔEPE | 95% CI | flip | AE | 3PE | Solve med | '
              'Total med |')
    rule = '|---|---|--:|--:|:-:|:-:|--:|--:|--:|--:|'

    def fmt(r, star=False):
        name = f"**{r['variant']}**" if star else r['variant']
        ci = ('ref' if r['variant'] == args.baseline
              else f"[{r['paired_ci_lo']:+.3f}, {r['paired_ci_hi']:+.3f}]")
        flip = '⚠' if r['sign_flip'] else ''
        t = (f"{r['solve_med_ms']:.1f} | {r['total_med_ms']:.1f} |"
             if r['solve_med_ms'] != '' else '- | - |')
        return (f"| {name} | {r['description']} | {r['epe']:.3f} | {r['epe_delta']:+.3f} | "
                f"{ci} | {flip} | {r['ae']:.2f} | {r['3pe_pct']:.1f} | {t}")

    for tier in ('removal', 'p1', 'p2', 'sens', 'protocol'):
        members = [r for r in rows if r['tier'] == tier]
        if not members:
            continue
        lines += [f'## {tier}', '']
        for axis in dict.fromkeys(r['axis'] for r in members):
            group = sorted((r for r in members
                            if r['axis'] == axis and r['variant'] != args.baseline),
                           key=lambda r: r['epe'])
            if not group:
                continue
            lines += [f'### {axis}', '', header, rule, fmt(reference, star=True)]
            lines += [fmt(r) for r in group]
            lines.append('')

    flips = [r['variant'] for r in rows if r['sign_flip']]
    if flips:
        lines += ['## Sign flips across sequences', '',
                  'These axes change direction between sequences, so no single pooled number '
                  'describes them. Inspect the per-sequence `d_<sequence>` columns in the CSV '
                  'before drawing any conclusion.', '',
                  *(f'- `{v}`' for v in flips), '']

    (out_dir / f'{label}_tables.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'{len(rows)} variants over {len(sequences)} sequences -> {csv_path}')
    if flips:
        print(f'sign flips: {", ".join(flips)}')
    missing = [n for n in meta if n not in runs]
    if missing:
        print(f'not yet scored ({len(missing)}): {", ".join(sorted(missing)[:12])}'
              + (' ...' if len(missing) > 12 else ''))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
