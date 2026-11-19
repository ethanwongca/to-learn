"""Read-only local web page. Run: python view.py -> http://127.0.0.1:8765"""
import html
import re
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from string import Template
from urllib.parse import unquote

import core

HOST, PORT = "127.0.0.1", 8765
esc = html.escape

CSS = """
:root{--bg:#FAF9F5;--surface:#FFFFFF;--text:#1F1E1D;--muted:#6B6A65;--border:#E8E6DC;--accent:#C96442;
--accent-ink:#A9502F;--level-0:#E8E6DC;--level-fill:#5A7D6A;--radius:12px;
--serif:ui-serif,Georgia,"Times New Roman",serif;--sans:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 var(--sans)}
nav,main{max-width:760px;margin:0 auto;padding:0 20px}
nav{display:flex;gap:24px;align-items:baseline;padding-top:28px}
.wordmark{font-family:var(--serif);font-size:1.4rem;margin-right:auto}
main{padding-bottom:64px}
a{color:var(--accent-ink)}
a:focus-visible{outline:2px solid var(--accent-ink);outline-offset:3px;border-radius:4px}
h1,h2,h3{font-family:var(--serif);font-weight:400;line-height:1.25;margin:0 0 .4em}
h1{font-size:2rem;margin-top:40px}h2{font-size:1.35rem;margin-top:8px}h3{font-size:1.2rem}
p{margin:0 0 .5em}.muted{color:var(--muted)}.small{font-size:.875rem}
.card{display:block;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
padding:22px;margin:16px 0;color:inherit;text-decoration:none}
a.card:hover{border-color:var(--accent)}
.badge{display:inline-block;border:1px solid var(--accent);color:var(--accent-ink);border-radius:999px;
padding:0 10px;font-size:.875rem}
.bar{height:8px;background:var(--level-0);border-radius:4px;overflow:hidden;margin:10px 0}
.bar span{display:block;height:100%;background:var(--level-fill)}
.mastery{display:flex;gap:3px}.mastery span{width:18px;height:8px;border-radius:2px;background:var(--level-0)}
.mastery span.on{background:var(--level-fill)}
ul,ol{margin:0;padding-left:1.4em}.plain{list-style:none;padding:0}
.rows li{display:grid;grid-template-columns:1fr auto 12rem 7.5rem;gap:12px;align-items:center;
padding:10px 0;border-top:1px solid var(--border)}
@media(max-width:640px){.rows li{grid-template-columns:1fr auto}}
.warn li{font-family:ui-monospace,monospace;font-size:.875rem}
"""

PAGE = Template("""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>$title</title><style>$css</style></head>
<body><nav aria-label="Main"><span class="wordmark">Learn</span><a href="/">Today</a><a href="/calendar">Calendar</a></nav>
<main>$body</main></body></html>""")


def bar(pct, label):
    return (f'<div class="bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{pct}" '
            f'aria-label="{esc(label)}"><span style="width:{pct}%"></span></div>')


def mastery(level):
    segs = "".join(f'<span class="{"on" if i < level else ""}"></span>' for i in range(5))
    return (f'<div class="mastery" role="progressbar" aria-valuemin="0" aria-valuemax="5" aria-valuenow="{level}" '
            f'aria-valuetext="Level {level} of 5: {core.LEVELS[level]}">{segs}</div>')


def relative(d, today):
    n = (d - today).days
    return "today" if n == 0 else f"in {core.plural(n, 'day')}" if n > 0 else f"{core.plural(-n, 'day')} overdue"


def warnings(topics):
    errs = [e for t in topics for e in t.errors]
    if not errs:
        return ""
    items = "".join(f"<li>{esc(e)}</li>" for e in errs)
    return f'<section class="card warn"><h2>Skipped malformed lines</h2><ul class="plain">{items}</ul></section>'


def home(topics, today):
    due = core.queue(topics, today, limit=10**9)
    hour = datetime.now().hour
    greet = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    out = [f"<h1>{greet}</h1><p class='muted'>{today:%A, %B} {today.day}, {today.year}</p>"]
    if due:
        items = "".join(f"<li>{esc(c.name)} <span class='muted small'>{esc(c.topic)} / {esc(c.group)} · L{c.level}"
                        f"</span></li>" for c in due[:5])
        up = f"<p><span class='badge'>{len(due)} due today</span></p><ol>{items}</ol>"
    else:
        nxt = min((c.next for c in core.all_concepts(topics) if c.next > today), default=None)
        when = "" if not nxt else f" Next review {nxt:%A}." if (nxt - today).days < 7 else f" Next review {nxt}."
        up = f"<p>All caught up.{when}</p>"
    out.append(f"<section class='card' aria-labelledby='up'><h2 id='up'>Up next</h2>{up}</section>")
    out.append("<section aria-labelledby='tp'><h2 id='tp' style='margin-top:32px'>Topics</h2>")
    for t in topics:
        pct, n = core.percent(t.concepts), sum(c.next <= today for c in t.concepts)
        meta = [f"{pct}%", f"{n} due"]
        if t.deadline:
            d = (t.deadline - today).days
            meta.append("deadline today" if d == 0 else f"{core.plural(d, 'day')} to deadline" if d > 0
                        else f"deadline passed {core.plural(-d, 'day')} ago")
        src = f"<p class='muted small'>{esc(t.source)}</p>" if t.source else ""
        out.append(f"<a class='card' href='/topic/{esc(t.slug)}'><h3>{esc(t.name)}</h3>{src}"
                   f"{bar(pct, t.name + ' progress')}<p class='small muted'>{' · '.join(meta)}</p></a>")
    if not topics:
        out.append("<p class='muted'>No topics yet. Ask Claude to add one.</p>")
    out.append("</section>")
    return "".join(out) + warnings(topics)


def topic_page(t, today):
    pct = core.percent(t.concepts)
    info = " · ".join(([esc(t.source)] if t.source else []) + ([f"deadline {t.deadline}"] if t.deadline else []))
    out = [f"<h1>{esc(t.name)}</h1><p class='muted'>{info}</p>{bar(pct, 'Overall progress')}"
           f"<p class='small muted'>{pct}% overall</p>"]
    for g, cs in t.groups().items():
        gp = core.percent(cs)
        rows = "".join(f"<li><span>{esc(c.name)}</span>{mastery(c.level)}<span class='small muted'>"
                       f"{core.LEVELS[c.level]}</span><span class='small'>{relative(c.next, today)}</span></li>"
                       for c in cs)
        out.append(f"<section class='card'><h2>{esc(g)}</h2>{bar(gp, g + ' progress')}"
                   f"<p class='small muted'>{gp}%</p><ul class='plain rows'>{rows}</ul></section>")
    return "".join(out) + warnings([t])


def calendar_page():
    path = core.ROOT / "calendar.txt"
    if not path.exists():
        core.write_calendar()
    sections = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(" ") and line.strip() and sections:
            sections[-1][1].append(line.strip())
        elif line.strip():
            sections.append((line.strip(), []))
    out = ["<h1>Calendar</h1>"]
    for head, items in sections:
        if items:
            lis = "".join(f"<li>{esc(i)}</li>" for i in items)
            out.append(f"<section class='card'><h2>{esc(head)}</h2><ul>{lis}</ul></section>")
        else:
            out.append(f"<p class='muted'>{esc(head)}</p>")
    return "".join(out)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        today, status = date.today(), 200
        try:
            topics = core.load_all()
            path = unquote(self.path.split("?")[0])
            m = re.fullmatch(r"/topic/([^/]+)", path)
            t = m and next((t for t in topics if t.slug == m[1]), None)
            if path == "/":
                body = home(topics, today)
            elif path == "/calendar":
                body = calendar_page()
            elif t:
                body = topic_page(t, today)
            else:
                status, body = 404, "<h1>Not found</h1><p><a href='/'>Back to today</a></p>"
            due = sum(c.next <= today for c in core.all_concepts(topics))
        except Exception as e:
            status, body, due = 500, f"<h1>Something went wrong</h1><p>{esc(str(e))}</p>", 0
        page = PAGE.substitute(title=f"({due}) Learn" if due else "Learn", css=CSS, body=body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"http://{HOST}:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
