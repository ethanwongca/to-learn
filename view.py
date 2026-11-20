"""Read-only local web page. Run: python view.py -> http://127.0.0.1:8765
Restarts itself when view.py or core.py is saved; a second `python view.py` replaces the running one."""
import html
import os
import re
import sys
import threading
import time
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from string import Template
from urllib.parse import quote, unquote

import core

HOST, PORT = "127.0.0.1", 8765
esc = html.escape

CSS = """
:root{--bg:#F3EAD7;--surface:#FFF9EE;--text:#2B1A12;--muted:#735C48;--border:#E2D3B8;--accent:#D9502B;
--accent-ink:#A8361A;--level-0:#E9DCC3;--level-fill:#E5762C;--radius:16px;--ink:#3A2418;--cream:#FFF3DC;
--shadow:5px 5px 0 var(--border);--press:3px 3px 0 var(--ink);
--brown:#8C3B1F;--red:#D9502B;--orange:#EE8A2E;--mustard:#F3B83C;
--stripes:linear-gradient(180deg,var(--brown) 0 25%,var(--red) 25% 50%,var(--orange) 50% 75%,var(--mustard) 75%);
--sunset:linear-gradient(90deg,var(--red),var(--orange),var(--mustard));
--serif:Futura,"Avenir Next","Century Gothic","Trebuchet MS",sans-serif;
--sans:"Avenir Next",ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 var(--sans)}
.wrap{max-width:760px;margin:0 auto;padding:0 20px}
main{padding-bottom:64px}
a{color:var(--accent-ink)}
a:focus-visible{outline:2px solid var(--accent-ink);outline-offset:3px;border-radius:4px}
.top{background:var(--ink);position:relative;padding-bottom:16px}
.top::after{content:"";position:absolute;left:0;right:0;bottom:0;height:16px;background:var(--stripes)}
.top .wrap{display:flex;align-items:center;gap:28px;min-height:68px}
.brand{display:flex;align-items:center;gap:10px;font-family:var(--serif);font-size:1.35rem;font-weight:500;
letter-spacing:.04em;color:var(--cream);text-decoration:none}.brand svg{display:block}
.top nav{display:flex;gap:8px;margin-right:auto}
.top nav a,.btn{font:500 .8rem/1 var(--serif);text-transform:uppercase;letter-spacing:.1em;text-decoration:none;
white-space:nowrap;border-radius:999px;padding:9px 16px;border:2px solid transparent}
.top nav a{color:#D9C7A8}
.top nav a:hover{color:var(--cream);border-color:rgba(243,184,60,.5)}
.top nav a[aria-current=page]{color:var(--ink);background:var(--mustard);border-color:var(--mustard)}
.top a:focus-visible{outline-color:var(--mustard)}
.btn{display:inline-block;color:var(--ink);background:var(--orange);border-color:var(--ink);box-shadow:var(--press);
transition:transform .08s,box-shadow .08s}
.btn:hover{transform:translate(-1px,-1px);box-shadow:4px 4px 0 var(--ink)}
.btn:active{transform:translate(2px,2px);box-shadow:1px 1px 0 var(--ink)}
.top .btn{background:var(--mustard);border-color:var(--mustard);box-shadow:3px 3px 0 var(--red)}
.top .btn:hover{box-shadow:4px 4px 0 var(--red)}.top .btn:active{box-shadow:1px 1px 0 var(--red)}
.top .btn[aria-current=page]{background:var(--orange);border-color:var(--orange)}
@media(max-width:520px){.top .wrap{gap:10px}.top nav{gap:2px}.top nav a,.btn{padding:8px 10px;letter-spacing:.06em}
.brand{font-size:0}.brand svg{width:28px;height:28px}}
h1,h2,h3{font-family:var(--serif);font-weight:500;line-height:1.25;margin:0 0 .4em}
h1{font-size:2rem;margin-top:40px}h2{font-size:1.35rem}h3{font-size:1.2rem;margin:0}
.section-title{margin-top:40px}
.section-title::before{content:"";display:block;width:56px;height:6px;border-radius:3px;background:var(--sunset);
margin-bottom:12px}
p{margin:0 0 .5em}.muted{color:var(--muted)}.small{font-size:.875rem}
.card{display:block;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
padding:22px;margin:16px 0;color:inherit;text-decoration:none;box-shadow:var(--shadow)}
a.card:hover{border-color:var(--accent);box-shadow:5px 5px 0 var(--mustard)}
.head{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.pct{font-family:var(--serif);font-size:1.2rem;color:var(--muted)}
.badge{background:var(--accent-ink);color:var(--cream);border-radius:999px;padding:3px 11px;
font:500 .75rem/1.2 var(--serif);text-transform:uppercase;letter-spacing:.08em;white-space:nowrap}
.bar{height:8px;background:var(--level-0);border-radius:4px;overflow:hidden;margin:10px 0}
.bar span{display:block;height:100%;background:var(--sunset)}
.mastery{display:flex;gap:3px}.mastery span{width:18px;height:8px;border-radius:2px;background:var(--level-0)}
.mastery span.on{background:var(--level-fill)}.mastery span.on:nth-child(1){background:var(--brown)}
.mastery span.on:nth-child(2){background:var(--red)}.mastery span.on:nth-child(5){background:var(--mustard)}
ul,ol{margin:0;padding-left:1.4em}.plain{list-style:none;padding:0}
.plain>li{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:10px 0;
border-top:1px solid var(--border)}
.plain>li:first-child{border-top:0}
.plain>li>a.row{display:flex;justify-content:space-between;align-items:center;gap:16px;width:100%;
color:inherit;text-decoration:none;border-radius:6px}
.plain>li>a.row:hover span:first-child{color:var(--accent-ink);text-decoration:underline}
.head h2 a{color:inherit;text-decoration:none}.head h2 a:hover{color:var(--accent-ink)}
.plain>li>div,.plain>li>a>div{min-width:0}
.plain>li>div>span,.plain>li>a>div>span{display:block;overflow-wrap:anywhere}
.rows>li{display:grid;grid-template-columns:1fr auto 12rem 7.5rem;gap:12px}
@media(max-width:640px){.rows>li{grid-template-columns:1fr auto}}
.overdue{color:var(--accent-ink)}.when{white-space:nowrap}
.steps{list-style:none;padding:0;counter-reset:s}
.steps>li{counter-increment:s;position:relative;padding-left:44px;margin-bottom:22px}
.steps>li::before{content:counter(s);position:absolute;left:0;top:0;width:30px;height:30px;border-radius:50%;
background:var(--red);color:var(--cream);box-shadow:2px 2px 0 var(--ink);display:grid;place-items:center;
font:500 .95rem/1 var(--serif)}
.steps>li:nth-child(4n+2)::before{background:var(--orange);color:var(--ink)}
.steps>li:nth-child(4n+3)::before{background:var(--mustard);color:var(--ink)}
.steps>li:nth-child(4n+4)::before{background:var(--brown)}
code,pre{font:.875rem/1.5 ui-monospace,Menlo,Consolas,monospace}
code{background:var(--level-0);border-radius:4px;padding:1px 5px}
pre{background:var(--ink);color:#FBE6C2;border-left:6px solid var(--orange);border-radius:10px;padding:14px 16px;
overflow-x:auto;margin:8px 0 0;white-space:pre-wrap;box-shadow:var(--shadow)}
details>summary{list-style:none;cursor:pointer}details>summary::-webkit-details-marker{display:none}
details>summary:focus-visible{outline:2px solid var(--accent-ink);outline-offset:3px;border-radius:4px}
.chev::before{content:"\\25B8";display:inline-block;width:1.1em;text-align:center;color:var(--accent);transition:transform .15s}
details[open]>summary .chev::before{transform:rotate(90deg)}
details.card:not([open]) .bar{margin-bottom:0}
details.sub{border:1px solid var(--border);border-left:5px solid var(--orange);border-radius:10px;margin-top:10px;background:var(--bg)}
details.sub:nth-of-type(3n+2){border-left-color:var(--red)}details.sub:nth-of-type(3n+3){border-left-color:var(--mustard)}
details.sub>summary:hover .chev{color:var(--accent-ink)}
details.sub>summary{display:flex;justify-content:space-between;gap:12px;padding:10px 14px}
details.sub h3{font-family:var(--sans);color:var(--muted);margin:6px 14px 0}
details.sub ul{padding:0 14px 8px}
.warn{border-left:6px solid var(--red)}
.warn li{font-family:ui-monospace,monospace;font-size:.875rem}
"""

LOGO_PATHS = ('<path d="M5 3V28H29" stroke="#D9502B"/><path d="M11 3V22H29" stroke="#EE8A2E"/>'
              '<path d="M17 3V16H29" stroke="#F3B83C"/>')
LOGO = ('<svg width="32" height="32" viewBox="0 0 32 32" aria-hidden="true" fill="none" stroke-linecap="round" '
        f'stroke-linejoin="round" stroke-width="4">{LOGO_PATHS}</svg>')
# Same striped L on a brown tile so it reads on light and dark browser tabs.
FAVICON = "data:image/svg+xml," + quote(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#3A2418"/>'
    '<g transform="translate(3 3) scale(.82)" fill="none" stroke-linecap="round" stroke-linejoin="round" '
    f'stroke-width="4.4">{LOGO_PATHS}</g></svg>')

PAGE = Template("""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">
<link rel="icon" type="image/svg+xml" href="$favicon">
<title>$title</title><style>$css</style></head>
<body><header class="top"><div class="wrap"><a class="brand" href="/">$logo Learn</a>
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


def when(d, today):
    n = (d - today).days
    return "today" if n == 0 else f"in {core.plural(n, 'day')}" if n > 0 else f"{core.plural(-n, 'day')} overdue"


def relative(d, today):
    return f"<span class='small when{' overdue' if d < today else ''}'>{when(d, today)}</span>"


def dates(t, today):
    """'deadline in 3 days · next reading today' style summary of a topic's header dates."""
    return [f"{what} {when(d, today)}" for what, d in (("next reading", t.next_reading), ("deadline", t.deadline)) if d]


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
        slug = {t.name: t.slug for t in topics}
        items = "".join(f"<li><a class='row' href='/topic/{esc(slug.get(c.topic, ''))}'><div><span>{esc(c.name)}</span>"
                        f"<span class='muted small'>{esc(c.topic)} · {esc(c.group)} · L{c.level}</span></div>"
                        f"{relative(c.next, today)}</a></li>"
                        for c in core.queue(topics, today, limit=5))
        up = f"<span class='badge'>{len(due)} due today</span></div><ul class='plain'>{items}</ul>"
    else:
        nxt = min((c.next for c in core.all_concepts(topics) if c.next > today), default=None)
        when = "" if not nxt else f" Next review {nxt:%A}." if (nxt - today).days < 7 else f" Next review {nxt}."
        up = f"</div><p class='muted'>All caught up.{when}</p>"
    out.append(f"<section class='card' aria-labelledby='up'><div class='head'>"
               f"<h2 id='up'><a href='/calendar'>Up next →</a></h2>{up}</section>")
    out.append("<section aria-labelledby='tp'><h2 id='tp' class='section-title'>Topics</h2>")
    for t in topics:
        pct, meta = core.percent(t.concepts), [f"{len(core.due(t.concepts, today))} due"] + dates(t, today)
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
    info = " · ".join([esc(t.source)] * bool(t.source) + dates(t, today))
    out = [f"<h1>{esc(t.name)}</h1><p class='muted'>{info}</p>{bar(pct, 'Overall progress')}"
           f"<p class='small muted'>{pct}% overall</p>"]
    # Groups start collapsed so a long book reads as a short outline; only the first one with reviews due opens.
    opened = False
    for g, cs in t.groups().items():
        gp, nd = core.percent(cs), len(core.due(cs, today))
        is_open, opened = bool(nd) and not opened, opened or bool(nd)
        rows = "".join(f"<li><span>{esc(c.name)}</span>{mastery(c.level)}<span class='small muted'>"
                       f"{core.LEVELS[c.level]}</span>{relative(c.next, today)}</li>" for c in cs)
        meta = " · ".join([core.plural(len(cs), "concept")] + [f"{nd} due"] * bool(nd))
        out.append(f"<details class='card'{' open' * is_open}><summary><div class='head'><h2 class='chev'>{esc(g)}</h2>"
                   f"<span class='pct'>{gp}%</span></div>{bar(gp, g + ' progress')}"
                   f"<p class='small muted'>{meta}</p></summary><ul class='plain rows'>{rows}</ul></details>")
    return "".join(out) + warnings([t])


def day_box(head, events, concepts):
    """One day's main box: readings/deadlines on top, then a collapsed sub-box per topic, grouped by concept."""
    out = [f"<section class='card'><div class='head'><h2>{esc(head)}</h2>"
           f"<span class='badge'>{core.plural(len(concepts), 'review')}</span></div>" if concepts else
           f"<section class='card'><h2>{esc(head)}</h2>"]
    if events:
        out.append("<ul class='plain'>" + "".join(f"<li><strong>{esc(e)}</strong></li>" for e in events) + "</ul>")
    by_topic = {}
    for c in concepts:
        by_topic.setdefault(c.topic, {}).setdefault(c.group, []).append(c)
    for topic, groups in by_topic.items():
        n = sum(map(len, groups.values()))
        inner = "".join(f"<h3 class='small'>{esc(g)}</h3><ul class='plain'>"
                        + "".join(f"<li><span>{esc(c.name)}</span><span class='small muted'>L{c.level}</span></li>"
                                  for c in cs) + "</ul>" for g, cs in groups.items())
        out.append(f"<details class='sub'><summary><span class='chev'>{esc(topic)}</span><span class='small muted'>"
                   f"{core.plural(len(groups), 'group')} · {core.plural(n, 'concept')}</span></summary>{inner}</details>")
    return "".join(out) + "</section>"


def calendar_page(topics, today):
    # Built fresh from the topic files (same days as calendar.txt) so hand edits show up immediately.
    days = core.calendar_days(topics, today)
    out = ["<div class='head'><h1>Calendar</h1><a class='btn' href='/calendar.ics' download>Download .ics</a></div>",
           "<p class='muted small'>Import into Google, Apple or Outlook Calendar to get a reminder on review days. "
           "Re-download after sessions; dates move as you learn.</p>"]
    out += [day_box(*day) for day in days] or ["<p class='muted'>Nothing scheduled in the next 14 days.</p>"]
    return "".join(out)


def add_page(today):
    return f"""<h1>Add a book or papers</h1>
<p class="muted">Your tutor adds them one chapter or paper at a time. It proposes an outline, you confirm it,
and it writes the file. The next chapter or paper is due a week later unless you name another date.</p>
<section class="card"><ol class="steps">
<li><strong>Open your tutor in this folder.</strong> Run <code>claude</code> here (or Codex) and approve the
<code>learn</code> server the first time.</li>
<li><strong>Say what you just read.</strong> Start with one chapter, or one paper for a theme:
<pre>Add Statistical Rethinking ch. 1 as a topic. Deadline 2027-02-19.
Add "Attention Is All You Need" to a new topic, Transformer papers.</pre></li>
<li><strong>Review the outline.</strong> It lists 1-3 general concepts per chapter with 2-5 big ideas each (10 max).
Say yes, or ask for changes.</li>
<li><strong>Come back here.</strong> The new topic shows up under Today. Every concept starts at level 0, due today.</li>
</ol></section>
<h2 class="section-title">Next chapter or paper</h2>
<p>When it's due, your tutor reminds you. Read it, then:</p>
<pre>Add ch. 2 of Statistical Rethinking. Next one due 2026-12-10.</pre>
<h2 class="section-title">Or write the file yourself</h2>
<p>Create <code>topics/&lt;name&gt;.txt</code>. One concept per line: <code>name | level | next review</code>.</p>
<pre>topic: Statistical Rethinking
source: McElreath
deadline: 2027-02-19
next reading: {today}

[Ch. 1 · Probability foundations]
Bayes' rule             | 0 | {today}
Conditional probability | 0 | {today}</pre>"""


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Lets a newer `python view.py` take over the port. The custom header can't be sent cross-site
        # without a CORS preflight, so other web pages can't shut this down.
        if self.path == "/__quit" and self.headers.get("X-Learn") == "quit":
            self.send(200, b"bye", "text/plain")
            threading.Thread(target=self.server.shutdown, daemon=True).start()
        else:
            self.send(404, b"", "text/plain")

    def do_GET(self):
        today, status = date.today(), 200
        path = unquote(self.path.split("?")[0])
        try:
            topics = core.load_all()
            if path == "/calendar.ics":
                return self.send(200, core.ics_text(topics, today).encode(), "text/calendar; charset=utf-8",
                                 {"Content-Disposition": 'attachment; filename="learn.ics"'})
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
            title=f"({due}) Learn" if due else "Learn", css=CSS, body=body, logo=LOGO, favicon=FAVICON,
            nav=link("/", "Today", path) + link("/calendar", "Calendar", path),
            add=link("/add", "+ Add reading", path, "btn")).encode()
        self.send(status, page, "text/html; charset=utf-8")

    def send(self, status, body, ctype, headers=None):
        self.send_response(status)
        for k, v in {"Content-Type": ctype, "Content-Length": str(len(body)), **(headers or {})}.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


WATCH = [core.ROOT / "view.py", core.ROOT / "core.py"]


def mtimes():
    return [f.stat().st_mtime if f.exists() else 0 for f in WATCH]


def watch(server):
    """Restart the process when the code changes (topic files are re-read on every request anyway)."""
    start = mtimes()
    while time.sleep(1) or mtimes() == start:
        pass
    print("Code changed, restarting...", flush=True)
    server.server_close()
    os.execv(sys.executable, [sys.executable] + sys.argv)


def take_over():
    """Ask an already-running view.py to quit, then wait for the port to free up."""
    import urllib.request
    try:
        req = urllib.request.Request(f"http://{HOST}:{PORT}/__quit", method="POST", headers={"X-Learn": "quit"})
        urllib.request.urlopen(req, timeout=2).read()
    except OSError:
        return False
    for _ in range(20):
        time.sleep(0.25)
        try:
            return ThreadingHTTPServer((HOST, PORT), Handler)
        except OSError:
            pass
    return False


if __name__ == "__main__":
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        server = take_over()
        if not server:
            raise SystemExit(f"Port {PORT} is busy with something else. Free it with: lsof -ti :{PORT} | xargs kill")
        print("Replaced the view.py that was already running.", flush=True)
    print(f"http://{HOST}:{PORT}  (auto-restarts on code changes, Ctrl+C to stop)", flush=True)
    threading.Thread(target=watch, args=(server,), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
