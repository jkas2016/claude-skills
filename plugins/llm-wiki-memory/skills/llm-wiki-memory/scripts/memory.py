"""Shared helpers for the documented simple frontmatter schema; Python stdlib only."""
import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

ROOTS = ("user", "feedback", "project", "reference", "projects")
FIELDS = ("name", "description", "type", "tags", "aliases", "created", "updated")
STATUSES = ("active", "archived", "superseded")
SKIP = {"README.md", "MEMORY.md"}


def vault():
    value = os.environ.get("LLM_WIKI_PATH", "")
    if not value or not Path(value).is_dir():
        raise ValueError("LLM_WIKI_PATH 미설정/없음")
    return Path(value).resolve()


def inside(root, rel):
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts or "\\" in str(rel):
        raise ValueError(f"상대경로만 허용: {rel}")
    path = root / p
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"vault 밖 경로: {rel}")
    cursor = root
    for part in p.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f"symlink 경로 금지: {rel}")
    return path


def note_path(root, rel):
    p = Path(rel)
    if not p.parts or p.parts[0] not in ROOTS or p.suffix != ".md" or p.name in SKIP:
        raise ValueError(f"메모리 노트 경로 아님: {rel}")
    return inside(root, rel)


def split_note(text):
    text = text.replace("\r\n", "\n")
    match = re.match(r"\A---\n(.*?)\n---(?:\n|$)", text, re.S)
    if not match:
        raise ValueError("frontmatter 없음")
    raw, meta = match.group(1), {}
    for key, value in re.findall(r"^([A-Za-z_][\w-]*):[ \t]*(.*)$", raw, re.M):
        if key in meta:
            raise ValueError(f"중복 frontmatter 필드: {key}")
        quote, escaped = "", False
        for i, char in enumerate(value):
            if escaped:
                escaped = False
            elif char == "\\" and quote == '"':
                escaped = True
            elif quote:
                if char == quote:
                    quote = ""
            elif char in "'\"":
                quote = char
            elif char == "#" and (i == 0 or value[i - 1].isspace()):
                value = value[:i].rstrip()
                break
        try:
            parsed = json.loads(value)
            meta[key] = str(parsed).lower() if isinstance(parsed, bool) else parsed
        except (ValueError, TypeError):
            meta[key] = value.strip("'\"")
    return raw, meta, text[match.end():].lstrip("\n")


def edit_note(text, fields, body=None):
    raw, _, old_body = split_note(text)
    for key, value in fields.items():
        pattern = rf"^{re.escape(key)}:.*(?:\n[ \t]+.*)*"
        if value is None:
            raw = re.sub(pattern + r"\n?", "", raw, flags=re.M)
            continue
        line = f"{key}: {json.dumps(value, ensure_ascii=False)}"
        if re.search(pattern, raw, re.M):
            raw = re.sub(pattern, lambda _: line, raw, flags=re.M)
        else:
            raw += "\n" + line
    return f"---\n{raw.strip()}\n---\n\n{old_body if body is None else body.strip() + chr(10)}"


@dataclass
class Note:
    rel: str
    text: str
    meta: dict
    body: str
    hook: str = ""

    @property
    def status(self):
        return self.meta.get("status", "active")

    @property
    def project(self):
        parts = Path(self.rel).parts
        return parts[1] if parts[0] == "projects" and len(parts) > 2 else ""

    def summary(self):
        summary = " ".join(str(self.hook or self.meta.get("description") or self.rel).split())
        if len(summary) > 240:
            summary = summary[:237] + "..."
        return f"- [{self.rel}] {summary} (status={self.status})\n"


def load_notes(root):
    hooks = {}
    index = inside(root, "MEMORY.md")
    if index.exists():
        for rel, hook in re.findall(r"\]\(([^)]+\.md)\)\s*[—-]\s*(.*)", index.read_text(encoding="utf-8")):
            hooks[rel] = hook
    notes = []
    for directory in ROOTS:
        for p in sorted(inside(root, directory).rglob("*.md")):
            if p.name in SKIP:
                continue
            rel = p.relative_to(root).as_posix()
            text = note_path(root, rel).read_text(encoding="utf-8")
            _, meta, body = split_note(text)
            notes.append(Note(rel, text, meta, body, hooks.get(rel, "")))
    return notes


def select(notes, keywords=(), project=None, include_inactive=False):
    kws = sorted(set(k.casefold() for term in keywords for k in term.split() if k))
    ranked = []
    for n in notes:
        if not include_inactive and n.status != "active":
            continue
        if project is not None and n.project and n.project != project:
            continue
        metadata = " ".join(str(n.meta.get(k, "")) for k in ("name", "description", "tags", "aliases"))
        metadata += " " + n.hook
        score = sum(10 * (k in metadata.casefold()) + 4 * (k in n.rel.casefold())
                    + (k in n.body.casefold()) for k in kws)
        if kws and not score:
            continue
        ranked.append((score, int(bool(project and n.project == project)), n))
    return [n for _, _, n in sorted(ranked, key=lambda row: (-row[0], -row[1], row[2].rel))]


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("양수 필요")
    return number


def budget(value):
    number = positive(value)
    if number < 256:
        raise argparse.ArgumentTypeError("최소 256 bytes")
    return number


def emit(text, max_bytes, whole_lines=False):
    encoded = text.encode("utf-8")
    if len(encoded) > max_bytes:
        suffix = b"\n[omitted: byte budget; narrow search or raise --max-bytes]\n"
        prefix = encoded[:max_bytes - len(suffix)].decode("utf-8", errors="ignore")
        if whole_lines:
            prefix = prefix.rsplit("\n", 1)[0] + "\n" if "\n" in prefix else ""
        text = prefix + suffix.decode()
    sys.stdout.write(text)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if path.exists():
            os.chmod(temp, path.stat().st_mode & 0o777)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


@contextmanager
def locked(root):
    path = inside(root, ".memory-lock")
    try:
        path.mkdir()
    except FileExistsError:
        raise ValueError("다른 쓰기 작업/남은 lock: .memory-lock (실행 중인지 확인 후 복구)")
    try:
        yield
    finally:
        path.rmdir()


def today():
    return dt.date.today().isoformat()


def cli(main):
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        sys.exit(1)
