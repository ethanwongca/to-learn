import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import core  # noqa: E402
import view  # noqa: E402

TODAY = date(2026, 11, 19)


class TestPages(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig, core.ROOT = core.ROOT, Path(self._tmp.name)
        (core.ROOT / "topics").mkdir()
        (core.ROOT / "topics" / "t.txt").write_text(
            "topic: T\n\n[G]\nOld  | 1 | 2026-11-17\nLater | 2 | 2026-11-21\nbroken line\n", encoding="utf-8")
        self.topics = core.load_all()

    def tearDown(self):
        core.ROOT = self._orig
        self._tmp.cleanup()

    def test_home(self):
        h = view.home(self.topics, TODAY)
        self.assertIn("1 due today", h)
        self.assertIn("2 days overdue", h)
        self.assertIn("/topic/t", h)
        self.assertIn("topics/t.txt:6:", h)

    def test_topic_and_calendar_are_fresh(self):
        self.assertIn("in 2 days", view.topic_page(self.topics[0], TODAY))
        cal = view.calendar_page(self.topics, TODAY)  # no calendar.txt on disk: built from topic files
        self.assertIn("Overdue", cal)
        self.assertIn("2026-11-21 Sat", cal)

    def test_calendar_links_ics(self):
        self.assertIn("href='/calendar.ics'", view.calendar_page(self.topics, TODAY))

    def test_add_page_and_empty_state(self):
        self.assertIn("2026-11-19", view.add_page(TODAY))
        self.assertIn("href='/add'", view.home([], TODAY))


if __name__ == "__main__":
    unittest.main()
