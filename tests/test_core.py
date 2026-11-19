import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import core  # noqa: E402

TODAY = date(2026, 11, 19)
EXAMPLE = REPO / "topics" / "example-bayesian-inference.txt"


class TempRoot(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = core.ROOT
        core.ROOT = Path(self._tmp.name)
        (core.ROOT / "topics").mkdir()

    def tearDown(self):
        core.ROOT = self._orig
        self._tmp.cleanup()

    def write(self, name, text):
        (core.ROOT / "topics" / name).write_text(text, encoding="utf-8", newline="\n")

    def read(self, name):
        return (core.ROOT / "topics" / name).read_text(encoding="utf-8")


class TestRoundTrip(unittest.TestCase):
    def test_example_is_byte_identical(self):
        t = core.parse_topic(EXAMPLE)
        self.assertEqual(t.errors, [])
        self.assertEqual(core.render(t).encode("utf-8"), EXAMPLE.read_bytes())


class TestMalformed(TempRoot):
    TEXT = ("topic: T\n\n[G]\n"
            "Good one  | 1 | 2026-11-19\n"
            "No pipes here\n"
            "Bad level | 9 | 2026-11-19\n"
            "Bad date  | 2 | 2026-13-40\n")

    def test_reported_kept_and_no_crash(self):
        self.write("t.txt", self.TEXT)
        t = core.load_all()[0]
        self.assertEqual(len(t.concepts), 1)
        self.assertEqual(len(t.errors), 3)
        self.assertIn("topics/t.txt:5:", t.errors[0])
        self.assertIn("topics/t.txt:5:", core.today_text(today=TODAY))
        self.assertIn("topics/t.txt:6:", core.list_topics_text(today=TODAY))
        out = core.update_text("Good one", 3, today=TODAY)
        self.assertTrue(out.startswith("Good one: 1 -> 3"), out)
        text = self.read("t.txt")
        for bad in ("No pipes here", "Bad level | 9 | 2026-11-19", "Bad date  | 2 | 2026-13-40"):
            self.assertIn(bad, text)


class TestInterval(TempRoot):
    def test_each_level(self):
        self.write("t.txt", "topic: T\n\n[G]\nX | 0 | 2026-11-19\n")
        for level, days in {0: 1, 1: 2, 2: 4, 3: 7, 4: 14, 5: 30}.items():
            core.update_text("X", level, today=TODAY)
            c = core.load_all()[0].concepts[0]
            self.assertEqual((c.level, c.next), (level, TODAY + timedelta(days)))


class TestMixing(TempRoot):
    def setUp(self):
        super().setUp()
        self.write("a.txt", "topic: A\n\n[G1]\na1 | 0 | 2026-11-10\na2 | 1 | 2026-11-11\na3 | 2 | 2026-11-12\n"
                            "\n[G2]\nb1 | 0 | 2026-11-15\nb2 | 0 | 2026-11-16\nb3 | 0 | 2026-11-17\n")
        self.write("b.txt", "topic: B\n\n[G1]\nc1 | 3 | 2026-11-13\nc2 | 0 | 2026-11-19\nfuture | 0 | 2026-12-01\n")

    def test_no_repeats_deterministic_limit(self):
        q = core.queue(core.load_all(), TODAY, limit=100)
        keys = [(c.topic, c.group) for c in q]
        self.assertEqual(len(q), 8)
        self.assertNotIn("future", [c.name for c in q])
        for i in range(len(keys) - 1):
            if keys[i] == keys[i + 1]:  # only allowed when no other group has items left
                self.assertTrue(all(k == keys[i] for k in keys[i:]))
        self.assertEqual([c.name for c in q], [c.name for c in core.queue(core.load_all(), TODAY, limit=100)])
        self.assertEqual([c.name for c in q[:3]], ["a1", "c1", "b1"])
        self.assertEqual(len(core.queue(core.load_all(), TODAY, limit=3)), 3)
        self.assertEqual(len(core.today_text(limit=3, today=TODAY).splitlines()), 3)


class TestTools(TempRoot):
    def test_update_ambiguous(self):
        self.write("a.txt", "topic: A\n\n[G]\nShared | 0 | 2026-11-19\n")
        self.write("b.txt", "topic: B\n\n[H]\nshared | 0 | 2026-11-19\n")
        out = core.update_text("Shared", 2, today=TODAY)
        self.assertTrue(out.startswith("Error:"), out)
        self.assertIn("A / G", out)
        self.assertIn("B / H", out)
        self.assertTrue(core.update_text("Shared", 2, topic="b", today=TODAY).startswith("shared: 0 -> 2"))

    def test_add_concepts(self):
        self.write("a.txt", "topic: A\n\n[G]\nOne | 0 | 2026-11-19\n\n[Other]\nZed | 0 | 2026-11-19\n")
        out = core.add_concepts_text("A", "g", "Two\none\nThree\nTwo", today=TODAY)
        self.assertEqual(out, "Added 2 to A / G (2 duplicates skipped).")
        out = core.add_concepts_text("a", "New group", "Four", today=TODAY)
        self.assertEqual(out, "Added 1 to A / New group.")
        groups = core.load_all()[0].groups()
        self.assertEqual([c.name for c in groups["G"]], ["One", "Two", "Three"])
        self.assertEqual([c.name for c in groups["New group"]], ["Four"])
        self.assertEqual(groups["New group"][0].next, TODAY)

    def test_calendar_regenerated_after_update(self):
        self.write("a.txt", "topic: A\n\n[G]\nOne | 0 | 2026-11-19\n")
        cal = core.ROOT / "calendar.txt"
        self.assertFalse(cal.exists())
        core.update_text("One", 2, note="ok", today=TODAY)
        self.assertIn("2026-11-23 Mon\n  One (A / G) — L2", cal.read_text(encoding="utf-8"))
        self.assertIn("| A | One | 0 -> 2 | ok", (core.ROOT / "log.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
