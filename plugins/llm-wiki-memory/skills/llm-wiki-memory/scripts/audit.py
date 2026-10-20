#!/usr/bin/env python3
"""Read-only maintenance candidates, never deletion verdicts. JSON includes source hashes."""
import argparse
import datetime as dt
import difflib
import json
import re
from memory import cli, digest, load_notes, note_path, positive, vault


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stale-days', type=positive, default=180)
    ap.add_argument('--long-bytes', type=positive, default=6000)
    args = ap.parse_args()
    root = vault()
    notes = load_notes(root)
    active = [n for n in notes if n.status == 'active']
    candidates = []
    for n in active:
        reasons = []
        if len(n.body.encode('utf-8')) > args.long_bytes:
            reasons.append('long: consider compact rule + separate historical detail')
        if re.search(r'구현 완료|구현완료|이력 보존|현행이 아니다|\bcompleted\b|\bsuperseded\b', n.body, re.I):
            reasons.append('completion-language: verify which decisions still apply')
        try:
            age = (dt.date.today() - dt.date.fromisoformat(str(n.meta.get('updated', '')))).days
            if age >= args.stale_days:
                reasons.append(f'review-age: {age} days; age is not evidence of invalidity')
        except ValueError:
            reasons.append('invalid updated date')
        if reasons:
            candidates.append({'paths': [n.rel], 'reasons': reasons})
    for i, a in enumerate(active):
        for b in active[i + 1:]:
            # Compare within the same scope only. Similarity is a review aid, not semantics.
            if a.project != b.project:
                continue
            norm_a, norm_b = ' '.join(a.body.split()), ' '.join(b.body.split())
            exact = bool(norm_a) and norm_a == norm_b
            descriptions = [str(n.meta.get('description', '')).casefold() for n in (a, b)]
            score = difflib.SequenceMatcher(None, *descriptions).ratio()
            if exact or (all(descriptions) and score >= .72):
                candidates.append({'paths': [a.rel, b.rel], 'reasons': [
                    'duplicate-body' if exact else f'similar-description: {score:.2f}; inspect scope/exceptions']})
    print(json.dumps({'notes': len(notes), 'active': len(active),
                      'notice': 'Candidates only. Preserve scope, exceptions, provenance; never retire by age alone.',
                      'sha256': {n.rel: digest(note_path(root, n.rel).read_bytes()) for n in notes},
                      'candidates': candidates}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    cli(main)
