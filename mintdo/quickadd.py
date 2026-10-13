"""Quick-add parser.

Lets you type everything in one line:

    "!1 buy flowers #gift tomorrow every week"

Produces: priority=1, tags=['gift'], due=tomorrow, repeat='weekly',
title='buy flowers'.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

_PRIORITY = re.compile(r"(?:^|\s)!([1-4])(?=\s|$)", re.I)
_TAG = re.compile(r"(?:^|\s)#([A-Za-z0-9_-]{1,32})")
_REPEAT = re.compile(
    r"(?:^|\s)every\s+(day|weekday|weekdays|week|month)s?(?=\s|$)", re.I)
_ISO = re.compile(r"(?:^|\s)(\d{4}-\d{2}-\d{2})(?=\s|$)")
_SLASH = re.compile(r"(?:^|\s)(\d{1,2})/(\d{1,2})(?=\s|$)")

_WEEKDAYS = {
    "mon": 0, "monday": 0, "tue": 1, "tues": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2, "thu": 3, "thur": 3, "thurs": 3,
    "thursday": 3, "fri": 4, "friday": 4, "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}

_REPEAT_MAP = {
    "day": "daily", "week": "weekly", "month": "monthly",
    "weekday": "weekdays", "weekdays": "weekdays",
}

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                 "Saturday", "Sunday"]


def _next_weekday(target: int) -> date:
    """Next occurrence of a weekday, strictly after today."""
    d = date.today()
    delta = (target - d.weekday()) % 7
    if delta == 0:
        delta = 7
    return d + timedelta(days=delta)


def parse(text: str) -> dict:
    """Extract metadata tokens from *text*; return clean task fields."""
    result = {"title": text.strip(), "priority": 0, "tags": [],
              "due": None, "repeat": ""}
    if not text or not text.strip():
        return result
    s = " " + text.strip() + " "

    m = _PRIORITY.search(s)
    if m:
        result["priority"] = int(m.group(1))
        s = s[:m.start()] + " " + s[m.end():]

    result["tags"] = [t.lower() for t in _TAG.findall(s)]
    if result["tags"]:
        s = _TAG.sub(" ", s)

    m = _REPEAT.search(s)
    if m:
        result["repeat"] = _REPEAT_MAP.get(m.group(1).lower(), "daily")
        s = s[:m.start()] + " " + s[m.end():]

    today = date.today()
    m = _ISO.search(s)
    if m:
        try:
            d = date.fromisoformat(m.group(1))
            if d >= today:
                result["due"] = d.isoformat()
                s = s[:m.start()] + " " + s[m.end():]
        except ValueError:
            pass

    if result["due"] is None:
        m = _SLASH.search(s)
        if m:
            try:
                d = date(today.year, int(m.group(1)), int(m.group(2)))
                if d < today:
                    d = date(today.year + 1, int(m.group(1)), int(m.group(2)))
                result["due"] = d.isoformat()
                s = s[:m.start()] + " " + s[m.end():]
            except ValueError:
                pass

    if result["due"] is None:
        for word, delta in (("today", 0), ("tomorrow", 1), ("tonight", 0)):
            m = re.search(r"(?:^|\s)" + word + r"(?=\s|$)", s, re.I)
            if m:
                result["due"] = (today + timedelta(days=delta)).isoformat()
                s = s[:m.start()] + " " + s[m.end():]
                break
        else:
            for word, idx in _WEEKDAYS.items():
                m = re.search(r"(?:^|\s)" + word + r"(?=\s|$)", s, re.I)
                if m:
                    result["due"] = _next_weekday(idx).isoformat()
                    s = s[:m.start()] + " " + s[m.end():]
                    break

    result["title"] = re.sub(r"\s+", " ", s).strip()
    return result
