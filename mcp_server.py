"""MCP server (stdio): thin wrapper over core.py. Every tool returns plain text."""
from functools import wraps

from mcp.server.fastmcp import FastMCP

import core

mcp = FastMCP("learn")


def safe(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # never crash the server; report as text
            return f"Error: {e}"
    return wrapper


@mcp.tool()
@safe
def today(limit: int = 10) -> str:
    """Today's mixed review queue (due and overdue concepts, interleaved across groups)."""
    return core.today_text(limit)


@mcp.tool()
@safe
def list_topics() -> str:
    """All topics with overall %, due count and deadline."""
    return core.list_topics_text()


@mcp.tool()
@safe
def show_topic(topic: str) -> str:
    """ASCII skill map for one topic (name or slug), grouped by general concept."""
    return core.show_topic_text(topic)


@mcp.tool()
@safe
def update(concept: str, level: int, note: str = "", topic: str = "") -> str:
    """Set a concept's level (0-5), reschedule its next review, and append to the log."""
    return core.update_text(concept, level, note, topic)


@mcp.tool()
@safe
def add_topic(name: str, outline: str, source: str = "", deadline: str = "") -> str:
    """Create a topic file. outline: '[General concept]' lines, then one concept per line
    (optionally 'name | level | YYYY-MM-DD'; defaults to level 0, due today)."""
    return core.add_topic_text(name, outline, source, deadline)


@mcp.tool()
@safe
def add_concepts(topic: str, general: str, concepts: str) -> str:
    """Append newline-separated concepts under a general concept (created if missing; duplicates skipped)."""
    return core.add_concepts_text(topic, general, concepts)


@mcp.tool()
@safe
def log_note(text: str) -> str:
    """Append a free-form note to log.txt."""
    return core.log_note_text(text)


@mcp.tool()
@safe
def tutor_skill() -> str:
    """Return the Socratic Tutor skill (skills/socratic-tutor/SKILL.md). Follow it exactly."""
    return core.tutor_skill_text()


if __name__ == "__main__":
    mcp.run()
