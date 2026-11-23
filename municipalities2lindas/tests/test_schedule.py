from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

from municipalities2lindas.src.schedule import DEFAULT_SCHEDULE, main, matches, should_run


class ShouldRunTests(unittest.TestCase):
    def test_default_runs_on_second(self):
        self.assertEqual(DEFAULT_SCHEDULE, "2 * *")
        self.assertTrue(should_run(None, date(2026, 12, 2)))
        self.assertFalse(should_run(None, date(2026, 12, 3)))

    def test_blank_uses_default(self):
        self.assertTrue(should_run("", date(2026, 12, 2)))
        self.assertFalse(should_run("", date(2026, 12, 3)))

    def test_off(self):
        self.assertFalse(should_run("off", date(2026, 12, 2)))
        self.assertFalse(should_run("OFF", date(2026, 12, 2)))

    def test_lists_ranges_steps(self):
        self.assertTrue(should_run("1,15 * *", date(2026, 12, 15)))
        self.assertFalse(should_run("* 1-3 *", date(2026, 4, 2)))
        self.assertTrue(should_run("*/10 * *", date(2026, 12, 1)))
        self.assertTrue(should_run("*/10 * *", date(2026, 12, 11)))
        self.assertTrue(should_run("*/10 * *", date(2026, 12, 21)))
        self.assertFalse(should_run("*/10 * *", date(2026, 12, 2)))

    def test_stepped_wildcard_is_unrestricted_so_fields_combine_with_and(self):
        # 2026-11-19 is a Thursday with an odd day of month.
        self.assertFalse(matches("*/2 * 1", date(2026, 11, 19)))
        self.assertTrue(matches("*/2 * 4", date(2026, 11, 19)))

    def test_invalid_steps_and_items_raise(self):
        for expression in ("*/0 * *", "1-5/0 * *", "1,,2 * *", "a/2 * *", "5-2 * *"):
            with self.subTest(expression=expression):
                with self.assertRaises(ValueError):
                    matches(expression, date(2026, 12, 2))

    def test_dow_sunday_0_and_7(self):
        self.assertTrue(matches("* * 0", date(2026, 11, 22)))
        self.assertTrue(matches("* * 7", date(2026, 11, 22)))

    def test_dom_and_dow_restricted_is_or(self):
        self.assertTrue(matches("1 * 1", date(2026, 11, 23)))
        self.assertTrue(matches("1 * 1", date(2026, 12, 1)))
        self.assertFalse(matches("1 * 1", date(2026, 11, 24)))

    def test_malformed_raises(self):
        for expression in ("2 *", "x * *", "32 * *"):
            with self.subTest(expression=expression):
                with self.assertRaises(ValueError):
                    matches(expression, date(2026, 12, 2))


class CliTests(unittest.TestCase):
    def _run(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_prints_effective_schedule_and_result(self):
        with patch.dict(os.environ, {}, clear=True):
            code, out, err = self._run(["--expression", "2 * *", "--date", "2026-12-02"])
        self.assertEqual(code, 0)
        self.assertEqual(out, "schedule=2 * * date=2026-12-02 run=true\n")
        self.assertEqual(err, "")

    def test_defaults_to_utc_today(self):
        with patch.dict(os.environ, {}, clear=True):
            code, out, _ = self._run([])
        today = datetime.now(timezone.utc).date().isoformat()
        self.assertEqual(code, 0)
        self.assertIn(f"schedule=2 * * date={today} run=", out)

    def test_github_output_receives_run_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = os.path.join(tmp, "github_output")
            with patch.dict(os.environ, {"GITHUB_OUTPUT": output_path}, clear=True):
                self._run(["--date", "2026-12-02"])
                with open(output_path, encoding="utf-8") as fh:
                    self.assertEqual(fh.read(), "run=true\n")
                self._run(["--date", "2026-12-03"])
                with open(output_path, encoding="utf-8") as fh:
                    self.assertEqual(fh.read(), "run=true\nrun=false\n")

    def test_malformed_expression_exits_1(self):
        with patch.dict(os.environ, {}, clear=True):
            code, out, err = self._run(["--expression", "2 *", "--date", "2026-12-02"])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("ERROR: "))


if __name__ == "__main__":
    unittest.main()
