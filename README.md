# learn

A plain-text spaced-learning folder for working through books and topics: every concept, level and review date is stored in a `.txt` file you can read and edit yourself. Claude (or Codex) acts as a Socratic tutor through a tiny local MCP server, and a small local web page shows your progress and review calendar.

![Learn home page: today's review queue and topic progress](docs/screenshot.png)

## The web page

`python view.py` serves a read-only page at `http://127.0.0.1:8765`. It re-reads the topic files on every request, so whatever the tutor (or you) just changed shows up on refresh. The browser tab shows `(N) Learn` when N reviews are due.

- **Today:** the next 5 reviews, mixed across topics and chapters, with how overdue each one is. Click a row to open its topic, or **Up next →** to open the calendar. Below that is one card per topic with overall progress, due count, next reading and deadline.
- **Topic:** one collapsible box per chapter or paper with its own progress bar. Only the first box with reviews due starts open, so a long book reads as a short outline. Each concept has a 5-step mastery bar, a plain-English level ("can do with help") and its next review.
- **Calendar:** one box per day for the next two weeks, overdue first. Inside each day there is a collapsed box per topic ("2 groups · 6 concepts"), so a heavy day stays readable; open it to see the concepts by chapter. Readings and deadlines are listed at the top of their day.
- **+ Add reading:** the steps for adding the next chapter or paper.

| Topic page | Calendar |
|---|---|
| ![Topic page: collapsible chapter boxes with mastery bars](docs/topic.png) | ![Calendar: a box per day, with a collapsible box per topic](docs/calendar.png) |

## Quick start

```bash
git clone <repo> learn && cd learn
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python view.py        # open http://127.0.0.1:8765
```

`view.py` restarts itself when you save `view.py` or `core.py`. Running it again while an old copy is up replaces that copy instead of failing with "port busy". Stop it with Ctrl+C.

## Connect an AI client (no API key)

- **Claude Code:** run `claude` inside the folder. It picks up `.mcp.json` automatically; approve the `learn` server when prompted.

  ```json
  { "mcpServers": { "learn": { "command": "python", "args": ["mcp_server.py"] } } }
  ```

  If `python` doesn't resolve to the venv's Python (`claude mcp list` shows `learn … Failed to connect`), register it for just your machine with the venv's absolute path. This overrides `.mcp.json` without changing it:

  ```bash
  claude mcp add learn --scope local -- "$PWD/.venv/bin/python" "$PWD/mcp_server.py"
  ```

- **Claude Desktop:** add the same `learn` entry to `claude_desktop_config.json`, using the absolute path to the venv's Python as `command` and the absolute path to `mcp_server.py` in `args`. Then restart Claude Desktop.

- **Codex:** `codex mcp add learn -- /abs/path/.venv/bin/python /abs/path/mcp_server.py`, or add this to `~/.codex/config.toml`:

  ```toml
  [mcp_servers.learn]
  command = "/abs/path/.venv/bin/python"
  args = ["/abs/path/mcp_server.py"]
  ```

## Daily workflow

Ask "what's due?" → do a tutor session → levels update as you go → refresh the web page to see them.

## Adding a book or papers

Add one chapter at a time: "Add *Statistical Rethinking* ch. 1 as a topic." The tutor proposes an outline of general concepts (named by chapter, e.g. `[Ch. 1 · Probability foundations]`), confirms it with you, and creates the topic file.

Outlines stay coarse on purpose: 1-3 general concepts per chapter or paper, 2-5 concepts each. The tools reject more than 5 concepts in one general concept or more than 10 in one outline (`MAX_PER_GROUP` and `MAX_PER_READING` in `core.py`). A concept should be a big idea worth reviewing for weeks. Notation, worked examples and minor results go inside it. The next chapter is then due a week later (`next reading:`). When it's due, `today` and the calendar say so. Read it, then say "Add ch. 2", optionally with another date ("next one due 2026-12-10"). The 7-day default is `READING_DAYS` in `core.py`.

Papers work the same way: make a topic for a theme ("Transformer papers") and add one paper at a time, each as its own general concept, e.g. `[Vaswani 2017 · Self-attention]`.

The **+ Add reading** button on the web page shows these steps, plus how to write the file by hand.

## File format

`topics/<slug>.txt`:

```
topic: Bayesian Inference
source: Statistical Rethinking (McElreath)
deadline: 2027-02-19
next reading: 2026-11-27

[Ch. 1 · Probability foundations]
Bayes' rule             | 2 | 2026-11-21
Conditional probability | 3 | 2026-11-25
```

- `topic:` is required. `source:`, `deadline:` and `next reading:` (YYYY-MM-DD) are optional.
- `[General concept]` starts a group. Concept lines are `name | level (0-5) | next review date`.
- Blank lines and lines starting with `#` are ignored.

Hand edits are fine. Malformed lines are reported (in tool output and on the web page) and kept as they are. `calendar.txt` is generated; don't edit it. `log.txt` is an append-only session log.

## How scheduling and mixing work

After a review, the next review date is today plus:

| level | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| days | 1 | 2 | 4 | 7 | 14 | 30 |

New concepts start at level 0, due today. Today's queue interleaves due concepts round-robin across general concepts (most overdue first), so you don't review the same group twice in a row.

## Calendar reminders

The Calendar page has a **Download .ics** button (also at `http://127.0.0.1:8765/calendar.ics`). Each day with reviews, a next reading or a deadline becomes a 30-minute event at 09:00 (`REMIND_HOUR` in `core.py`) with a reminder. Overdue items land on today.

- **Google Calendar:** Settings → Import & export → Import, into a dedicated calendar (e.g. "Learn") with a default notification set: Google ignores reminders inside imported files. Dates move as you learn, so now and then delete that calendar's events and import a fresh file.
- **Apple Calendar:** File → New Calendar Subscription with the URL above refreshes on its own while `view.py` is running.

## Credits

- **Socratic Tutor skill:** adapted from Jane Street's skill in [janestreet/agent_skills](https://github.com/janestreet/agent_skills), used under the MIT License. Its copyright and license notice is kept in [`skills/socratic-tutor/LICENSE`](skills/socratic-tutor/LICENSE). The original text in `SKILL.md` is unchanged. Local additions (cross-topic synthesis, and "just tell me" never counting toward a level-up) are in its last section.
- **Learning principles:** drawn from *Make It Stick* (Brown, Roediger & McDaniel), *Ultralearning* (Young) and *A Mind for Numbers* (Oakley).
- **Look:** an original 1970s-inspired palette and striped "L" logo. No third-party logos, images or fonts are bundled: headings use Futura or Avenir Next when your system has them, and fall back to standard system fonts.
- **Screenshots:** made from the bundled example topic plus a demo topic. They don't show anyone's real reading list.

## License

MIT. See [LICENSE](LICENSE). The tutor skill keeps its own MIT notice in [`skills/socratic-tutor/LICENSE`](skills/socratic-tutor/LICENSE).
