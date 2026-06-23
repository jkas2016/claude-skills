"""doublestar-compatible glob matching (subset used by OpenCodeReview rules)."""
import re


def expand_braces(pattern):
    m = re.search(r"\{([^{}]*)\}", pattern)
    if not m:
        return [pattern]
    pre, post = pattern[: m.start()], pattern[m.end():]
    out = []
    for opt in m.group(1).split(","):
        out.extend(expand_braces(pre + opt + post))
    return out


def glob_to_regex(pattern):
    i, n, out = 0, len(pattern), []
    while i < n:
        c = pattern[i]
        if c == "*":
            if pattern.startswith("**/", i):
                out.append(r"(?:[^/]+/)*"); i += 3; continue
            if pattern.startswith("**", i):
                out.append(r".*"); i += 2; continue
            out.append(r"[^/]*"); i += 1; continue
        if c == "?":
            out.append(r"[^/]"); i += 1; continue
        out.append(re.escape(c)); i += 1
    return "".join(out)


def match_glob(pattern, path):
    return any(
        re.fullmatch(glob_to_regex(p), path) is not None
        for p in expand_braces(pattern)
    )
