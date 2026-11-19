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
.wrap{max-width:760px;margin:0 auto;padding:0 20px}
main{padding-bottom:64px}
a{color:var(--accent-ink)}
a:focus-visible{outline:2px solid var(--accent-ink);outline-offset:3px;border-radius:4px}
.top{background:var(--surface);border-bottom:1px solid var(--border)}
.top .wrap{display:flex;align-items:center;gap:28px}
.brand{font-family:var(--serif);font-size:1.35rem;color:var(--text);text-decoration:none}
.top nav{display:flex;gap:20px;margin-right:auto}
.top nav a{color:var(--muted);text-decoration:none;padding:16px 0;border-bottom:2px solid transparent}
.top nav a:hover{color:var(--text)}
.top nav a[aria-current=page]{color:var(--text);border-bottom-color:var(--accent)}
.btn{color:var(--accent-ink);border:1px solid var(--accent);border-radius:999px;padding:3px 14px;
font-size:.9rem;text-decoration:none;white-space:nowrap}
.btn:hover,.btn[aria-current=page]{background:#F6EAE4}
@media(max-width:480px){.top .wrap{gap:14px}.top nav{gap:14px}}
h1,h2,h3{font-family:var(--serif);font-weight:400;line-height:1.25;margin:0 0 .4em}
h1{font-size:2rem;margin-top:40px}h2{font-size:1.35rem}h3{font-size:1.2rem;margin:0}
.section-title{margin-top:36px}
p{margin:0 0 .5em}.muted{color:var(--muted)}.small{font-size:.875rem}
.card{display:block;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
padding:22px;margin:16px 0;color:inherit;text-decoration:none}
a.card:hover{border-color:var(--accent)}
.head{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.pct{font-family:var(--serif);font-size:1.2rem;color:var(--muted)}
.badge{border:1px solid var(--accent);color:var(--accent-ink);border-radius:999px;padding:0 10px;
font-size:.875rem;white-space:nowrap}
.bar{height:8px;background:var(--level-0);border-radius:4px;overflow:hidden;margin:10px 0}
.bar span{display:block;height:100%;background:var(--level-fill)}
.mastery{display:flex;gap:3px}.mastery span{width:18px;height:8px;border-radius:2px;background:var(--level-0)}
.mastery span.on{background:var(--level-fill)}
ul,ol{margin:0;padding-left:1.4em}.plain{list-style:none;padding:0}
.plain>li{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:10px 0;
border-top:1px solid var(--border)}
.plain>li:first-child{border-top:0}
.plain>li>div{min-width:0}.plain>li>div>span{display:block;overflow-wrap:anywhere}
.rows>li{display:grid;grid-template-columns:1fr auto 12rem 7.5rem;gap:12px}
@media(max-width:640px){.rows>li{grid-template-columns:1fr auto}}
.overdue{color:var(--accent-ink)}.when{white-space:nowrap}
.steps{list-style:none;padding:0;counter-reset:s}
.steps>li{counter-increment:s;position:relative;padding-left:44px;margin-bottom:22px}
.steps>li::before{content:counter(s);position:absolute;left:0;top:0;width:28px;height:28px;border-radius:50%;
border:1px solid var(--border);background:var(--surface);display:grid;place-items:center;font-family:var(--serif)}
code,pre{font:.875rem/1.5 ui-monospace,Menlo,Consolas,monospace}
pre{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:12px 14px;overflow-x:auto;
margin:8px 0 0;white-space:pre-wrap}
.warn li{font-family:ui-monospace,monospace;font-size:.875rem}
"""

PAGE = Template("""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>$title</title><style>$css</style></head>
<body><header class="top"><div class="wrap"><a class="brand" href="/">Learn</a>
<nav aria-label="Main">$nav</nav>$add</div></header>
<main class="wrap">$body</main></body></html>""")


def link(href, label, current, cls=""):
    cur = ' aria-current="page"' if href == current else ""
    return f'<a href="{href}"{cur}{f" class={cls!r}" if cls else ""}>{label}</a>'


def bar(pct, label):
    return (f'<div class="bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{pct}" '
            f'aria-label="{esc(label)}"><span style="width:{pct}%"></span></div>')


def mastery(level):
    segs = "".join(f'<span class="{"on" if i < level else ""}"></span>' for i in range(5))
    return (f'<div class="mastery" role="progressbar" aria-valuemin="0" aria-valuemax="5" aria-valuenow="{level}" '
            f'aria-valuetext="Level {level} of 5: {core.LEVELS[level]}">{segs}</div>')


def relative(d, today):
    n = (d - today).days
    text = "today" if n == 0 else f"in {core.plural(n, 'day')}" if n > 0 else f"{core.plural(-n, 'day')} overdue"
    return f"<span class='small when{' overdue' if n < 0 else ''}'>{text}</span>"


def warnings(topics):
    errs = [e for t in topics for e in t.errors]
    if not errs:
        return ""
    items = "".join(f"<li>{esc(e)}</li>" for e in errs)
    return f'<section class="card warn"><h2>Skipped malformed lines</h2><ul>{items}</ul></section>'


def home(topics, today):
    due = core.due(core.all_concepts(topics), today)
    hour = datetime.now().hour
    greet = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    out = [f"<h1>{greet}</h1><p class='muted'>{today:%A, %B} {today.day}, {today.year}</p>"]
    if due:
        items = "".join(f"<li><div><span>{esc(c.name)}</span><span class='muted small'>{esc(c.topic)} · "
                        f"{esc(c.group)} · L{c.level}</span></div>{relative(c.next, today)}</li>"
                        for c in core.queue(topics, today, limit=5))
        up = f"<span class='badge'>{len(due)} due today</span></div><ul class='plain'>{items}</ul>"
    else:
        nxt = min((c.next for c in core.all_concepts(topics) if c.next > today), default=None)
        when = "" if not nxt else f" Next review {nxt:%A}." if (nxt - today).days < 7 else f" Next review {nxt}."
        up = f"</div><p class='muted'>All caught up.{when}</p>"
    out.append(f"<section class='card' aria-labelledby='up'><div class='head'><h2 id='up'>Up next</h2>{up}</section>")
    out.append("<section aria-labelledby='tp'><h2 id='tp' class='section-title'>Topics</h2>")
    for t in topics:
        pct, meta = core.percent(t.concepts), [f"{len(core.due(t.concepts, today))} due"]
        if t.deadline:
            d = (t.deadline - today).days
            meta.append("deadline today" if d == 0 else f"{core.plural(d, 'day')} to deadline" if d > 0
                        else f"deadline passed {core.plural(-d, 'day')} ago")
        src = f"<p class='muted small'>{esc(t.source)}</p>" if t.source else ""
        out.append(f"<a class='card' href='/topic/{esc(t.slug)}'><div class='head'><h3>{esc(t.name)}</h3>"
                   f"<span class='pct'>{pct}%</span></div>{src}{bar(pct, t.name + ' progress')}"
                   f"<p class='small muted'>{' · '.join(meta)}</p></a>")
    if not topics:
        out.append("<div class='card'><p>No topics yet.</p><a href='/add'>Add your first book →</a></div>")
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
                       f"{core.LEVELS[c.level]}</span>{relative(c.next, today)}</li>" for c in cs)
        out.append(f"<section class='card'><div class='head'><h2>{esc(g)}</h2><span class='pct'>{gp}%</span>"
                   f"</div>{bar(gp, g + ' progress')}<ul class='plain rows'>{rows}</ul></section>")
    return "".join(out) + warnings([t])


def calendar_page(topics, today):
    # Same text calendar.txt holds, built fresh so hand edits and date changes show up immediately.
    sections = []
    for line in core.calendar_text(topics, today).splitlines():
        if line.startswith(" ") and sections:
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


def add_page(today):
    return f"""<h1>Add a book</h1>
<p class="muted">Your tutor adds books for you. It proposes an outline, you confirm it, and it writes the file.</p>
<section class="card"><ol class="steps">
<li><strong>Open your tutor in this folder.</strong> Run <code>claude</code> here (or Codex) and approve the
<code>learn</code> server the first time.</li>
<li><strong>Say what you're reading.</strong> Include chapters and an optional deadline:
<pre>Add Statistical Rethinking ch. 1-6 as a topic. Deadline 2027-02-19.</pre></li>
<li><strong>Review the outline.</strong> It lists general concepts with 3-8 concepts each.
Say yes, or ask for changes.</li>
<li><strong>Come back here.</strong> The new topic shows up under Today. Every concept starts at level 0, due today.</li>
</ol></section>
<h2 class="section-title">Adding chapters later</h2>
<pre>Add ch. 7-9 of Statistical Rethinking to Bayesian Inference.</pre>
<h2 class="section-title">Or write the file yourself</h2>
<p>Create <code>topics/&lt;name&gt;.txt</code>. One concept per line: <code>name | level | next review</code>.</p>
<pre>topic: Statistical Rethinking
source: McElreath, ch. 1-6
deadline: 2027-02-19

[Probability foundations]
Bayes' rule             | 0 | {today}
Conditional probability | 0 | {today}</pre>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        today, status = date.today(), 200
        path = unquote(self.path.split("?")[0])
        try:
            topics = core.load_all()
            m = re.fullmatch(r"/topic/([^/]+)", path)
            t = m and next((t for t in topics if t.slug == m[1]), None)
            if path == "/":
                body = home(topics, today)
            elif path == "/calendar":
                body = calendar_page(topics, today)
            elif path == "/add":
                body = add_page(today)
            elif t:
                body = topic_page(t, today)
            else:
                status, body = 404, "<h1>Not found</h1><p><a href='/'>Back to today</a></p>"
            due = len(core.due(core.all_concepts(topics), today))
        except Exception as e:
            status, body, due = 500, f"<h1>Something went wrong</h1><p>{esc(str(e))}</p>", 0
        page = PAGE.substitute(
            title=f"({due}) Learn" if due else "Learn", css=CSS, body=body,
            nav=link("/", "Today", path) + link("/calendar", "Calendar", path),
            add=link("/add", "+ Add a book", path, "btn")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        raise SystemExit(f"Port {PORT} is busy. Is view.py already running? Open http://{HOST}:{PORT}")
    print(f"http://{HOST}:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
