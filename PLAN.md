# Build Spec: `learn` — a plain-text spaced-learning folder with an MCP tutor

Hand this file to Claude Code (or Codex) and say: **"Build this exactly as specified. No extra features."**

---

## 1. Goal

A single local folder for self-study (books or topics). Everything is stored in `.txt` files.
- A tiny **MCP server** lets Claude Code / Claude Desktop / Codex read and update those files.
- A tiny **local web page** shows progress and a calendar.
- The AI tutor is Claude itself, guided by the bundled **Socratic Tutor skill**.
- No API keys, no database, no cloud, no accounts.

## 2. Non-goals (do NOT build)

- No database, ORM, auth, user accounts, or multi-user support
- No JS framework, no build step, no CSS framework, no external fonts/CDNs
- No push or desktop notifications, no background daemons
- No LLM API calls from the code
- No FSRS/SM-2. Use the simple interval table below.
- No editing UI in the web page (it's read-only). Edit by hand or via Claude.

## 3. Requirements

- Python 3.10+
- One dependency: `mcp` (official Python SDK). The web page uses the standard library only.
- Works on macOS, Linux and Windows.

## 4. Folder layout

```
learn/
├── README.md
├── PLAN.md                      # this file
├── CLAUDE.md                    # instructions for Claude Code (see §10)
├── AGENTS.md                    # same content, for Codex
├── .mcp.json                    # Claude Code project MCP config
├── requirements.txt             # mcp
├── core.py                      # parsing, scheduling, mixing, file writes (shared)
├── mcp_server.py                # MCP tools (thin wrapper over core.py)
├── view.py                      # local web page (stdlib http.server)
├── skills/
│   └── socratic-tutor/
│       └── SKILL.md             # the tutor skill (text in §11)
├── topics/
│   └── example-bayesian-inference.txt
├── calendar.txt                 # generated, do not hand-edit
├── log.txt                      # append-only session log
└── tests/
    └── test_core.py
```

All paths resolve relative to the folder containing `core.py`. Never write outside it.

## 5. File formats

### 5.1 Topic file — `topics/<slug>.txt`

```
topic: Bayesian Inference
source: Statistical Rethinking (McElreath), ch. 1-6
deadline: 2027-02-19

[Probability foundations]
Bayes' rule | 2 | 2026-11-21
Conditional probability | 3 | 2026-11-25

[Hierarchical models]
Partial pooling | 0 | 2026-11-20
```

Rules:
- Header: `topic:` is required. `source:` and `deadline:` (YYYY-MM-DD) are optional.
- `[General concept]` starts a group. Every concept belongs to the group above it.
- Concept line: `name | level | next_review_date`
  - `level`: integer 0–5
  - date: `YYYY-MM-DD`
  - whitespace around `|` is ignored. `|` is not allowed inside names.
- Blank lines and lines starting with `#` are comments and are ignored.
- Slug: lowercase name, non-alphanumerics → `-`.
- **Round-trip:** after a parse then a write, the result must be byte-identical for a well-formed file. When writing, pad concept names so the `|` columns line up within each file.
- On a malformed line: skip it and report `filename:line: reason` in tool output and on the web page. Never crash, and never delete the bad line on write (keep it as-is).

### 5.2 Level meanings (from the skill)

```
0 unaware · 1 heard of it · 2 can follow along · 3 can do with help
4 can do independently · 5 can teach it / handle edge cases
```

### 5.3 `log.txt` (append-only)

```
2026-11-19 14:32 | Bayesian Inference | Bayes' rule | 2 -> 3 | recalled cold, shaky on base rates
2026-11-19 14:40 | note | finished ch. 2 simulation exercise
```

### 5.4 `calendar.txt` (generated after every write)

The next 14 days, plus an "Overdue" section at the top. It lists only days that have items.

```
Overdue
  Partial pooling (Bayesian Inference / Hierarchical models) — L0

2026-11-21 Sat
  Bayes' rule (Bayesian Inference / Probability foundations) — L2
```

## 6. Scheduling

When a concept is reviewed and given a level, set `next = today + INTERVAL[level]`:

| level | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| days | 1 | 2 | 4 | 7 | 14 | 30 |

New concepts start at level 0 with `next = today`. "Today" means the local date.

## 7. Mixing (today's queue)

1. Collect concepts from all topics where `next <= today`.
2. Group them by `(topic, general concept)`.
3. Inside each group, sort by: most overdue first, then lowest level, then file order.
4. Round-robin across groups so the same group never appears twice in a row when another group has items left. Order groups by their most overdue item.
5. Cap at `limit` (default 10).

This must be deterministic: the same files and date always give the same queue.

## 8. MCP server — `mcp_server.py`

Use `from mcp.server.fastmcp import FastMCP` and the stdio transport. All tools take plain arguments and **return plain text**. Every write regenerates `calendar.txt`.

| Tool | Args | Does | Returns (example) |
|---|---|---|---|
| `today` | `limit: int = 10` | Mixed queue (§7) | `1. Partial pooling — Bayesian Inference / Hierarchical models — L0 (1d overdue)` per line, or `Nothing due today. Next: 2026-11-21 (2 items).` |
| `list_topics` | — | All topics with overall % | `Bayesian Inference — 34% — 3 due — deadline 2027-02-19` |
| `show_topic` | `topic: str` | ASCII skill map, grouped by general concept, in the skill's map format | The bar map from §11 |
| `update` | `concept: str, level: int, note: str = "", topic: str = ""` | Set level, reschedule, append to log | `Bayes' rule: 2 -> 3. Next review 2026-11-26.` |
| `add_topic` | `name: str, outline: str, source: str = "", deadline: str = ""` | Create a topic file. `outline` uses the same `[General]` + one-concept-per-line text format (levels/dates optional, default to 0/today) | `Created topics/bayesian-inference.txt with 4 general concepts, 18 concepts.` |
| `add_concepts` | `topic: str, general: str, concepts: str` | Append newline-separated concepts under a general concept (create the group if missing; skip duplicates) | `Added 3 to Bayesian Inference / MCMC (1 duplicate skipped).` |
| `log_note` | `text: str` | Append a free-form note | `Logged.` |
| `tutor_skill` | — | Returns the contents of `skills/socratic-tutor/SKILL.md` | the skill text |

Matching rules:
- `topic` matches on name or slug, case-insensitive.
- `concept` matches by exact name (case-insensitive) across all topics. If more than one topic has it and no `topic` is given, return an error listing the candidates.
- Return errors as text starting with `Error:` rather than raising them.

Overall % for a topic = sum of levels / (5 × number of concepts).

## 9. Web page — `view.py`

- `python view.py` serves on `http://127.0.0.1:8765` (bind to localhost only) and prints that URL.
- Built on stdlib `http.server`. HTML comes from Python string templates with one inline `<style>` block. No JavaScript, except an optional `<meta http-equiv="refresh" content="60">`.
- The page re-reads the txt files on every request, so changes show up right away.
- Browser tab title: `(N) Learn` when N items are due, otherwise `Learn`. This is the "reminder".

### Pages

1. **`/` Home**
   - Greeting line plus the date.
   - **"Up next"** card: the first 5 items from `today()`, with a count ("7 due today"). Empty state: "All caught up. Next review Saturday."
   - **Topics** list: one card per topic, showing name, source, a progress bar (%), due count and days until the deadline. Each card links to its topic page.
2. **`/topic/<slug>`**
   - Topic title, source, deadline, and an overall progress bar.
   - One section per general concept, each with its own mini-progress.
   - Concept rows: name, a **5-segment mastery bar** (Khan-style: filled segments = level), a level label (e.g. "can do with help") and the next review date ("today", "in 3 days", "2 days overdue").
3. **`/calendar`**
   - Renders `calendar.txt` content as a clean list: Overdue first, then the dated days.

Top nav: `Learn` (wordmark, plain text) · `Today` · `Calendar`. Nothing else.

### Design tokens

The feel is calm, warm and editorial: generous whitespace, one accent color and Khan-style mastery bars. Use an original look. Don't copy logos, wordmarks or brand assets from any site.

```css
--bg: #FAF9F5;        /* warm off-white */
--surface: #FFFFFF;
--text: #1F1E1D;
--muted: #6B6A65;
--border: #E8E6DC;
--accent: #C96442;    /* muted clay: buttons, links, "due" badges */
--level-0: #E8E6DC;   /* empty segment */
--level-fill: #5A7D6A;/* filled mastery segment (sage) */
--radius: 12px;
--serif: ui-serif, Georgia, "Times New Roman", serif;      /* headings */
--sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; /* body */
```

- Max content width 760px, centered. Body 16px, line-height 1.6.
- Cards: white surface, 1px border, radius 12px, 20–24px padding, no heavy shadows.
- Headings use the serif font at regular weight (not bold).
- Mobile: single column, which works naturally since it's already one column.
- Accessibility: WCAG AA contrast, visible focus states, and semantic HTML (`<main>`, `<nav>`, `<section>`, `<progress>` or `role="progressbar"` with aria values).

## 10. `CLAUDE.md` / `AGENTS.md` (identical content)

```
You are the tutor for this folder.
- Session start: call `today`. If the user names a topic, call `show_topic`.
- Load the tutor rules with `tutor_skill` and follow them exactly
  (one question at a time, strict leveling, spaced review).
- After judging a concept, call `update(concept, level, note)`.
  Raise levels only per the skill's evaluation rules.
- When the user adds a book or chapters, propose an outline of
  [General concepts] with 3-8 concepts each, confirm it, then call
  `add_topic` or `add_concepts`.
- Never edit the txt files directly; use the tools.
- Keep responses brief.
```

## 11. Skill file — `skills/socratic-tutor/SKILL.md`

Copy the Socratic Tutor skill text verbatim (the author supplies it; it's the same text as the skill in the author's Claude preferences). Credit it in the README (§12).

## 12. README.md (must include)

1. **What it is** (2 sentences) and a screenshot placeholder.
2. **Quick start**
   ```bash
   git clone <repo> learn && cd learn
   python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   python view.py        # open http://127.0.0.1:8765
   ```
3. **Connect an AI client (no API key)**
   - **Claude Code:** open the folder with `claude`. The `.mcp.json` file is picked up automatically, so approve the `learn` server when prompted. `.mcp.json`:
     ```json
     { "mcpServers": { "learn": { "command": "python", "args": ["mcp_server.py"] } } }
     ```
     (Tell users to use the venv's python path if `python` doesn't resolve to it.)
   - **Claude Desktop:** add the same entry, with an **absolute path** to `mcp_server.py` and the venv python, to `claude_desktop_config.json`, then restart.
   - **Codex:** `codex mcp add learn -- /abs/path/.venv/bin/python /abs/path/mcp_server.py`, or add `[mcp_servers.learn]` with `command` and `args` to `~/.codex/config.toml`.
4. **Daily workflow:** "what's due?" → tutor session → levels update → check the web page.
5. **Adding a book:** "Add *Statistical Rethinking* ch. 1–6 as a topic."
6. **File format reference** (§5.1, short version) and a note that hand edits are fine.
7. **How scheduling and mixing work** (the table from §6 plus one sentence on mixing).
8. **Credits:** "Socratic Tutor skill adapted from Jane Street's skill; see `skills/socratic-tutor/SKILL.md`." (The author should add the source link.) Also mention that the learning principles draw on *Make It Stick*, *Ultralearning* and *A Mind for Numbers*.
9. **License:** MIT.

## 13. Tests — `tests/test_core.py` (stdlib `unittest` or pytest)

- Parse → write round-trip is byte-identical on the example file.
- Malformed lines are reported, kept on write, and don't crash anything.
- Interval table: each level 0–5 gives the correct next date (use a fixed "today").
- Mixing: no two items in a row from the same group when it's avoidable; output is deterministic; the limit is respected.
- `update` on an ambiguous concept returns an `Error:` listing the candidates.
- `add_concepts` skips duplicates and creates missing groups.
- `calendar.txt` is regenerated after `update`.

## 14. Build order

1. `core.py` and its tests (parser, writer, scheduler, mixer, calendar)
2. `mcp_server.py`, then a manual check with `npx @modelcontextprotocol/inspector python mcp_server.py` (optional)
3. `view.py`, and check all 3 pages in a browser
4. Example topic file, `CLAUDE.md`, `AGENTS.md`, `.mcp.json`, skill file
5. README

## 15. Done when

- `pip install -r requirements.txt && python view.py` works on a fresh clone.
- In Claude Code inside the folder, "what's due?" returns the mixed queue, a short tutor session updates the levels, and the web page shows the change on refresh.
- All tests pass. Total code stays under ~600 lines, excluding tests.
