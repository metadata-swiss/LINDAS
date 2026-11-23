"""Decide whether a daily scheduled run should proceed.

GitHub cron strings must be literal, so the workflow fires every day and this
gate reads a configurable cron-style expression (day-of-month, month,
day-of-week) to decide.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date, datetime, timezone
from typing import Optional, Set, Tuple

DEFAULT_SCHEDULE = "2 * *"

_RANGES = {"day-of-month": (1, 31), "month": (1, 12), "day-of-week": (0, 7)}
_DIGITS = re.compile(r"[0-9]+")


def _number(text: str, name: str) -> int:
    if not _DIGITS.fullmatch(text):
        raise ValueError(f"{name} value {text!r} is not a number")
    return int(text)


def _parse_field(text: str, name: str) -> Tuple[Set[int], bool]:
    """Return the allowed values for one field and whether it is restricted."""
    lo, hi = _RANGES[name]
    if not text:
        raise ValueError(f"empty {name} field")
    restricted = not text.startswith("*")  # cron: a leading "*" means unrestricted
    values: Set[int] = set()
    for item in text.split(","):
        if not item:
            raise ValueError(f"empty item in {name} field {text!r}")
        base, step = item, 1
        if "/" in item:
            base, step_text = item.split("/", 1)
            step = _number(step_text, name)
            if step == 0:
                raise ValueError(f"step must be positive in {name} field {text!r}")
        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            first, last = base.split("-", 1)
            start, end = _number(first, name), _number(last, name)
        elif "/" in item:
            raise ValueError(f"step needs '*' or a range in {name} field {text!r}")
        else:
            start = end = _number(base, name)
        if start > end:
            raise ValueError(f"reversed range in {name} field {text!r}")
        if not (lo <= start and end <= hi):
            raise ValueError(f"{name} value out of range {lo}-{hi} in {text!r}")
        values.update(range(start, end + 1, step))
    if name == "day-of-week":
        values = {0 if value == 7 else value for value in values}
    return values, restricted


def _parse(expression: str) -> Tuple[Tuple[Set[int], bool], ...]:
    fields = expression.split()
    if len(fields) != 3:
        raise ValueError(
            f"expected 3 fields (day-of-month month day-of-week), got {len(fields)}"
            f" in {expression!r}"
        )
    names = ("day-of-month", "month", "day-of-week")
    return tuple(_parse_field(field, name) for field, name in zip(fields, names))


def matches(expression: str, day: date) -> bool:
    """Return True if ``day`` matches the three-field cron-style expression."""
    (dom, dom_restricted), (months, _), (dow, dow_restricted) = _parse(expression)
    if day.month not in months:
        return False
    day_of_month_ok = day.day in dom
    cron_weekday = (day.weekday() + 1) % 7
    day_of_week_ok = cron_weekday in dow
    if dom_restricted and dow_restricted:
        return day_of_month_ok or day_of_week_ok
    return day_of_month_ok and day_of_week_ok


def _effective(expression: Optional[str]) -> str:
    text = (expression or "").strip()
    return text or DEFAULT_SCHEDULE


def should_run(expression: Optional[str], day: date) -> bool:
    """Return whether the scheduled run proceeds on ``day``.

    ``None`` or blank uses DEFAULT_SCHEDULE; ``off`` disables runs.
    """
    text = _effective(expression)
    if text.lower() == "off":
        return False
    return matches(text, day)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--expression", default=None)
    parser.add_argument("--date", type=date.fromisoformat, default=None)
    args = parser.parse_args(argv)

    day = args.date or datetime.now(timezone.utc).date()
    try:
        run = should_run(args.expression, day)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    result = "true" if run else "false"
    print(f"schedule={_effective(args.expression)} date={day.isoformat()} run={result}")
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as fh:
            fh.write(f"run={result}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
