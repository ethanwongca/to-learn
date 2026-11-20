"""Shared logic: parse/write topic files, scheduling, mixing, calendar, and tool actions."""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INTERVAL = {0: 1, 1: 2, 2: 4, 3: 7, 4: 14, 5: 30}
LEVELS = ["unaware", "heard of it", "can follow along", "can do with help",
          "can do independently", "can teach it / handle edge cases"]
DAYS = "Mon Tue Wed Thu Fri Sat Sun".split()
READING_DAYS = 7  # default pace: next chapter/paper due this many days after one is added
REMIND_HOUR = 9  # local start time of review events in calendar.ics
ENC = dict(encoding="utf-8", errors="surrogateescape")


@dataclass
class Concept:
    name: str
    level: int
    next: date
    group: str
    topic: str = ""
    order: tuple = ()


@dataclass
class Topic:
    path: Path
    name: str
    source: str = ""
    deadline: date | None = None
    next_reading: date | None = None
    entries: list = field(default_factory=list)  # raw str lines (kept as-is) or Concept
    errors: list = field(default_factory=list)

    @property
    def slug(self):
        return self.path.stem

    @property
    def concepts(self):
        return [e for e in self.entries if isinstance(e, Concept)]

    def groups(self):
        out = {}
        for e in self.entries:
            if isinstance(e, Concept):
                out[e.group].append(e)
            elif (g := group_name(e)) is not None:
                out.setdefault(g, [])
        return out


def topics_dir():
    return ROOT / "topics"


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def percent(concepts):
    return round(100 * sum(c.level for c in concepts) / (5 * len(concepts))) if concepts else 0


def due(concepts, today):
    return [c for c in concepts if c.next <= today]


def plural(n, word):
    return f"{n} {word}{'s' * (n != 1)}"


def parse_date(s):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s.strip()):
        return None
    try:
        return date.fromisoformat(s.strip())
    except ValueError:
        return None


def group_name(line):
    m = re.fullmatch(r"\[([^\[\]|]*)\]", line.strip())
    return m[1].strip() if m and m[1].strip() else None


def parse_concept(line, group, today=None):
    """Return (Concept, None) or (None, reason). With `today`, level and date are optional."""
    parts = [p.strip() for p in line.split("|")]
    if not parts[0]:
        return None, "empty concept name"
    if len(parts) > 3 or (today is None and len(parts) != 3):
        return None, "expected 'name | level | YYYY-MM-DD'"
    lvl = parts[1] if len(parts) > 1 else "0"
    if not re.fullmatch(r"[0-5]", lvl):
        return None, f"level must be 0-5, got {lvl!r}"
    d = parse_date(parts[2]) if len(parts) > 2 else today
    if d is None:
        return None, f"bad date {parts[2]!r}"
    return Concept(parts[0], int(lvl), d, group), None


def parse_topic(path):
    lines = path.read_text(**ENC).split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    t, group = Topic(path, ""), None
    for i, line in enumerate(lines, 1):
        s, bad = line.strip(), None
        if not s or s.startswith("#"):
            pass
        elif (g := group_name(s)) is not None:
            group = g
        elif s.startswith("["):
            bad = "bad group header"
        elif group is None:
            m = re.fullmatch(r"(topic|source|deadline|next reading):\s*(.*)", s)
            if not m:
                bad = "line before any [group]"
            elif m[1] == "topic":
                t.name = m[2]
            elif m[1] == "source":
                t.source = m[2]
            elif d := parse_date(m[2]):
                setattr(t, m[1].replace(" ", "_"), d)
            else:
                bad = f"bad {m[1]} {m[2]!r}"
        else:
            c, bad = parse_concept(s, group)
            if c:
                t.entries.append(c)
                continue
        if bad:
            t.errors.append(f"topics/{path.name}:{i}: {bad}")
        t.entries.append(line)
    if not t.name:
        t.errors.append(f"topics/{path.name}:1: missing 'topic:' header")
        t.name = path.stem
    return t


def render(t):
    w = max((len(c.name) for c in t.concepts), default=0)
    return "".join((f"{e.name.ljust(w)} | {e.level} | {e.next}" if isinstance(e, Concept) else e) + "\n"
                   for e in t.entries)


def load_all():
    topics = sorted(topics_dir().glob("*.txt")) if topics_dir().is_dir() else []
    out = []
    for ti, p in enumerate(topics):
        t = parse_topic(p)
        for ei, e in enumerate(t.entries):
            if isinstance(e, Concept):
                e.topic, e.order = t.name, (ti, ei)
        out.append(t)
    return out


def all_concepts(topics):
    return [c for t in topics for c in t.concepts]


def agenda(topics):
    """Sorted (date, label, is_review) for every review, next reading and deadline."""
    items = [(c.next, c.order, f"{c.name} ({c.topic} / {c.group}) — L{c.level}", True) for c in all_concepts(topics)]
    for ti, t in enumerate(topics):
        items += [(d, (ti, -1), f"{kind}: {t.name}", False)
                  for kind, d in (("Read next", t.next_reading), ("Deadline", t.deadline)) if d]
    return [(d, label, rev) for d, _, label, rev in sorted(items)]


def calendar_text(topics, today):
    items = agenda(topics)
    sections = []
    if over := [f"  {label}" for d, label, _ in items if d < today]:
        sections.append("Overdue\n" + "\n".join(over))
    for n in range(14):
        day = today + timedelta(n)
        if lines := [f"  {label}" for d, label, _ in items if d == day]:
            sections.append(f"{day} {DAYS[day.weekday()]}\n" + "\n".join(lines))
    return "\n\n".join(sections) + "\n" if sections else "Nothing scheduled in the next 14 days.\n"


def _ics_line(line):
    """Fold one content line to 75 octets (RFC 5545) without splitting a UTF-8 character; adds CRLF."""
    b, out = line.encode("utf-8", "replace"), []
    while len(b) > 75:
        cut = 75
        while b[cut] & 0xC0 == 0x80:
            cut -= 1
        out.append(b[:cut])
        b = b" " + b[cut:]
    return b"\r\n".join(out + [b]).decode() + "\r\n"


def ics_text(topics, today):
    """One timed event (with a reminder) per day that has reviews, readings or deadlines; overdue -> today."""
    days = {}
    for d, label, rev in agenda(topics):
        days.setdefault(max(d, today), []).append((label, rev))
    esc = lambda s: s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    stamp = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//learn//EN", "CALSCALE:GREGORIAN", "X-WR-CALNAME:Learn"]
    for d, items in sorted(days.items()):
        n = sum(rev for _, rev in items)
        summary = " · ".join([f"Learn: {plural(n, 'review')}"] * bool(n) + [label for label, rev in items if not rev])
        lines += ["BEGIN:VEVENT", f"UID:{d:%Y%m%d}@learn", f"DTSTAMP:{stamp}",
                  f"DTSTART:{d:%Y%m%d}T{REMIND_HOUR:02d}0000", "DURATION:PT30M", f"SUMMARY:{esc(summary)}",
                  f"DESCRIPTION:{esc(chr(10).join(label for label, _ in items))}",
                  "BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{esc(summary)}", "TRIGGER:PT0M", "END:VALARM",
                  "END:VEVENT"]
    return "".join(_ics_line(x) for x in lines + ["END:VCALENDAR"])


def write_calendar(today=None):
    (ROOT / "calendar.txt").write_text(calendar_text(load_all(), today or date.today()), **ENC, newline="\n")


def write_topic(t, today=None):
    t.path.write_text(render(t), **ENC, newline="\n")
    write_calendar(today)


def queue(topics, today, limit=10):
    groups = {}
    for c in due(all_concepts(topics), today):
        groups.setdefault((c.order[0], c.group), []).append(c)
    lists = [sorted(g, key=lambda c: (c.next, c.level, c.order)) for g in groups.values()]
    lists.sort(key=lambda g: (g[0].next, g[0].order))
    out = []
    while lists and len(out) < limit:
        for g in lists:
            out.append(g.pop(0))
        lists = [g for g in lists if g]
    return out[:limit]


def find_topic(topics, q):
    q = q.strip().lower()
    return next((t for t in topics if q in (t.name.lower(), t.slug)), None)


def _warn(text, topics):
    errs = [e for t in topics for e in t.errors]
    return text + ("\n\nSkipped malformed lines:\n" + "\n".join("  " + e for e in errs) if errs else "")


def _log(text):
    with open(ROOT / "log.txt", "a", **ENC, newline="\n") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M} | {' '.join(text.split())}\n")


def _clean(s):
    return " ".join(s.split())


def _reading(s, default):
    """Parse a next_reading argument: '' -> default, 'none' -> None. Returns (date|None, error|None)."""
    s = s.strip().lower()
    if not s or s == "none":
        return (default if not s else None), None
    return (d := parse_date(s)), None if d else "Error: next_reading must be YYYY-MM-DD or 'none'."


def set_next_reading(t, d):
    """Replace, insert or (d=None) remove the 'next reading:' header line."""
    head = next((i for i, e in enumerate(t.entries) if not isinstance(e, str) or group_name(e) is not None),
                len(t.entries))
    line = [f"next reading: {d}"] * bool(d)
    i = next((i for i in range(head) if t.entries[i].strip().startswith("next reading:")), None)
    if i is None:
        i = 1 + max((j for j in range(head) if t.entries[j].strip()), default=-1)
        t.entries[i:i] = line
    else:
        t.entries[i:i + 1] = line
    t.next_reading = d


# ---- tool actions (all return plain text) ----

def today_text(limit=10, today=None):
    today, topics = today or date.today(), load_all()
    q = queue(topics, today, limit)
    if q:
        text = "\n".join(
            f"{i}. {c.name} — {c.topic} / {c.group} — L{c.level} "
            f"({'due today' if c.next == today else f'{(today - c.next).days}d overdue'})"
            for i, c in enumerate(q, 1))
    else:
        future = [c.next for c in all_concepts(topics) if c.next > today]
        n = min(future, default=None)
        text = f"Nothing due today. Next: {n} ({plural(future.count(n), 'item')})." if n else "Nothing due today."
    text += "".join(f"\nRead next: {t.name} (due {t.next_reading})"
                    for t in topics if t.next_reading and t.next_reading <= today)
    return _warn(text, topics)


def list_topics_text(today=None):
    today, topics = today or date.today(), load_all()
    lines = [f"{t.name} — {percent(t.concepts)}% — {len(due(t.concepts, today))} due"
             + (f" — deadline {t.deadline}" if t.deadline else "")
             + (f" — next reading {t.next_reading}" if t.next_reading else "") for t in topics]
    return _warn("\n".join(lines) or "No topics yet.", topics)


def show_topic_text(topic):
    topics = load_all()
    t = find_topic(topics, topic)
    if not t:
        return f"Error: no topic matching {topic!r}."
    w = max([len(c.name) + 2 for c in t.concepts] + [20])
    bar = lambda pct: "█" * round(pct / 10) + "░" * (10 - round(pct / 10))
    mark = {4: "  * independent", 5: "  * can teach"}
    rule = "-" * (w + 40)
    head = f"Topic: {t.name}"
    out = [f"{head.ljust(w + 16)}overall: {bar(percent(t.concepts))} {percent(t.concepts)}%"]
    out += [f"Source: {t.source}"] * bool(t.source) + [f"Deadline: {t.deadline}"] * bool(t.deadline)
    out += [f"Next reading: {t.next_reading}"] * bool(t.next_reading)
    for g, cs in t.groups().items():
        out += [rule, f"[{g}]  {bar(percent(cs))} {percent(cs)}%"]
        out += [f"  {c.name.ljust(w)}[{bar(c.level * 20)}]  {c.level}/5  next {c.next}{mark.get(c.level, '')}"
                for c in cs]
    return _warn("\n".join(out + [rule]), [t])


def update_text(concept, level, note="", topic="", today=None):
    today, topics = today or date.today(), load_all()
    if not isinstance(level, int) or isinstance(level, bool) or not 0 <= level <= 5:
        return "Error: level must be an integer 0-5."
    pool = topics
    if topic:
        if not (t := find_topic(topics, topic)):
            return f"Error: no topic matching {topic!r}."
        pool = [t]
    hits = [(t, c) for t in pool for c in t.concepts if c.name.lower() == concept.strip().lower()]
    if not hits:
        return f"Error: no concept named {concept!r}" + (f" in {pool[0].name}." if topic else ".")
    if len(hits) > 1:
        return (f"Error: {concept!r} is ambiguous; pass topic. Candidates: "
                + "; ".join(f"{t.name} / {c.group}" for t, c in hits))
    t, c = hits[0]
    old, c.level, c.next = c.level, level, today + timedelta(INTERVAL[level])
    write_topic(t, today)
    _log(f"{t.name} | {c.name} | {old} -> {level}" + (f" | {note}" if note.strip() else ""))
    return _warn(f"{c.name}: {old} -> {level}. Next review {c.next}.", [t])


def add_topic_text(name, outline, source="", deadline="", next_reading="", today=None):
    today, name, source, deadline = today or date.today(), _clean(name), _clean(source), deadline.strip()
    slug = slugify(name)
    if not slug:
        return "Error: topic name is empty."
    path = topics_dir() / f"{slug}.txt"
    if path.exists():
        return f"Error: topics/{slug}.txt already exists. Use add_concepts."
    if deadline and not parse_date(deadline):
        return "Error: deadline must be YYYY-MM-DD."
    nxt, err = _reading(next_reading, today + timedelta(READING_DAYS))
    if err:
        return err
    t = Topic(path, name, entries=[f"topic: {name}"] + [f"source: {source}"] * bool(source)
              + [f"deadline: {deadline}"] * bool(deadline) + [f"next reading: {nxt}"] * bool(nxt))
    group, groups, seen = None, 0, set()
    for i, raw in enumerate(outline.splitlines(), 1):
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if (g := group_name(s)) is not None:
            t.entries += ["", f"[{g}]"]
            group, groups = g, groups + 1
            continue
        if group is None:
            return f"Error: outline line {i}: concept before any [General concept]."
        c, bad = parse_concept(s, group, today)
        if bad:
            return f"Error: outline line {i}: {bad}."
        if c.name.lower() not in seen:
            seen.add(c.name.lower())
            t.entries.append(c)
    if not t.concepts:
        return "Error: outline has no concepts."
    topics_dir().mkdir(exist_ok=True)
    write_topic(t, today)
    return (f"Created topics/{slug}.txt with {plural(groups, 'general concept')}, {plural(len(t.concepts), 'concept')}."
            + (f" Next reading due {nxt}." if nxt else ""))


def add_concepts_text(topic, general, concepts, next_reading="", today=None):
    today, topics = today or date.today(), load_all()
    if not (t := find_topic(topics, topic)):
        return f"Error: no topic matching {topic!r}."
    if not (general := group_name(f"[{_clean(general)}]")):
        return "Error: invalid general concept name."
    is_group = lambda e: isinstance(e, str) and group_name(e) is not None
    start = next((i for i, e in enumerate(t.entries) if is_group(e) and group_name(e).lower() == general.lower()), None)
    existing, new, dup = {c.name.lower() for c in t.concepts}, [], 0
    if start is not None:
        general = group_name(t.entries[start])
    # A new group means a new chapter/paper was read, so the next one is due a week from now.
    nxt, err = _reading(next_reading, t.next_reading if start is not None else today + timedelta(READING_DAYS))
    if err:
        return err
    for i, raw in enumerate(concepts.splitlines(), 1):
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        c, bad = parse_concept(s, general, today)
        if bad:
            return f"Error: concepts line {i}: {bad}."
        if c.name.lower() in existing:
            dup += 1
            continue
        existing.add(c.name.lower())
        new.append(c)
    if new:
        if start is None:
            t.entries += ["", f"[{general}]"]
            at = len(t.entries)
        else:
            end = next((j for j in range(start + 1, len(t.entries)) if is_group(t.entries[j])), len(t.entries))
            at = 1 + max(j for j in range(start, end) if not isinstance(t.entries[j], str) or t.entries[j].strip())
        t.entries[at:at] = new
    if new or nxt != t.next_reading:
        set_next_reading(t, nxt)
        write_topic(t, today)
    return (f"Added {len(new)} to {t.name} / {general}"
            + (f" ({plural(dup, 'duplicate')} skipped)" if dup else "") + "."
            + (f" Next reading due {nxt}." if nxt else ""))


def log_note_text(text):
    if not text.strip():
        return "Error: note is empty."
    _log(f"note | {text}")
    return "Logged."


def tutor_skill_text():
    p = ROOT / "skills" / "socratic-tutor" / "SKILL.md"
    return p.read_text(encoding="utf-8") if p.exists() else "Error: skills/socratic-tutor/SKILL.md not found."
