"""Metadata-only character bigram similarity for the save gate."""
from dataclasses import dataclass
from unicodedata import category

WARN = 0.12
BLOCK = 0.80
FIELDS = ('name', 'description', 'index_hook', 'aliases')


def field_text(meta, field):
    value = meta.get(field) or ''
    if field == 'aliases':
        if isinstance(value, str):
            value = [item.strip().strip("'\"") for item in value.strip('[]').split(',')]
        if isinstance(value, list):
            return ' '.join(map(str, value))
    return str(value)


def grams(text):
    chars = ''.join(char for char in text.casefold()
                    if not char.isspace() and not category(char).startswith('P'))
    return set(zip(chars, chars[1:]))


def score(left, right):
    left_fields = [field_text(left, field) for field in FIELDS]
    right_fields = [field_text(right, field) for field in FIELDS]
    pairs = zip(left_fields + [' '.join(left_fields)], right_fields + [' '.join(right_fields)])
    scores = []
    for left_text, right_text in pairs:
        a, b = grams(left_text), grams(right_text)
        scores.append(len(a & b) / len(a | b) if a or b else 0.0)
    return max(scores)


@dataclass(frozen=True)
class Candidate:
    rel: str
    score: float
    status: str
    level: str


def candidates(request, notes, project, *, warn, block):
    matches = []
    for note in notes:
        if note.project != project:
            continue
        value = score(request, note.meta)
        if value >= warn:
            level = 'block' if value >= block and note.status == 'active' and not note.rel.startswith('_archive/') else 'warn'
            matches.append(Candidate(note.rel, value, note.status, level))
    return sorted(matches, key=lambda candidate: (-candidate.score, candidate.rel))
