"""US equities (NYSE/Nasdaq) market clock — holiday- and early-close-aware.

Dependency-free: NYSE holidays are computed algorithmically (fixed dates with
Sat→Fri / Sun→Mon observance, floating Mondays/Thursdays, and Good Friday from
Easter), so it stays correct across years without a data file. Regular session
is 09:30–16:00 ET; half-days close 13:00 ET.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
_OPEN = time(9, 30)
_CLOSE = time(16, 0)
_EARLY_CLOSE = time(13, 0)
# The agent reviews on the :50 of each hour, 9:50 AM → 3:50 PM ET — deliberately
# past the 9:30 open (skip the volatile first minutes) and stopping a real cushion
# before the 4:00 close so the last order fills BEFORE the closing auction. :50
# gives the brain (2–5 min) a full margin before the top of the hour, every hour.
_AGENT_FIRST_H = 9         # first slot hour → 9:50
_AGENT_LAST_H = 15        # last slot hour → 15:50 (12 on half-days)
_AGENT_MIN = 50


def _easter(year: int) -> date:
    """Gregorian Easter Sunday (Anonymous algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """n-th `weekday` (Mon=0) of a month."""
    d = date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    return d + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    d = date(year, month, 28)
    while d.month == month:
        nxt = d + timedelta(days=1)
        if nxt.month != month:
            break
        d = nxt
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _observed(d: date, *, new_years: bool = False) -> date:
    """NYSE observance: Saturday holiday → observed Friday; Sunday → Monday.
    (New Year's Day is NOT pulled back to Dec 31 when it lands on Saturday.)"""
    if d.weekday() == 5:  # Saturday
        return d if new_years else d - timedelta(days=1)
    if d.weekday() == 6:  # Sunday
        return d + timedelta(days=1)
    return d


def nyse_holidays(year: int) -> set[date]:
    """Full-close NYSE holidays for `year`."""
    h = {
        _observed(date(year, 1, 1), new_years=True),      # New Year's Day
        _nth_weekday(year, 1, 0, 3),                       # MLK Day (3rd Mon Jan)
        _nth_weekday(year, 2, 0, 3),                       # Washington's Bday (3rd Mon Feb)
        _easter(year) - timedelta(days=2),                 # Good Friday
        _last_weekday(year, 5, 0),                         # Memorial Day (last Mon May)
        _nth_weekday(year, 9, 0, 1),                       # Labor Day (1st Mon Sep)
        _nth_weekday(year, 11, 3, 4),                      # Thanksgiving (4th Thu Nov)
        _observed(date(year, 12, 25)),                     # Christmas
        _observed(date(year, 7, 4)),                       # Independence Day
    }
    if year >= 2022:
        h.add(_observed(date(year, 6, 19)))               # Juneteenth
    # Saturday New Year's lands on a non-trading day — drop it so it isn't "closed today".
    return {d for d in h if d.weekday() < 5}


def early_closes(year: int) -> set[date]:
    """Half-days (13:00 ET close): July 3 (when a weekday & not the holiday),
    Friday after Thanksgiving, and Christmas Eve (when a weekday)."""
    out: set[date] = set()
    hols = nyse_holidays(year)
    jul3 = date(year, 7, 3)
    if jul3.weekday() < 5 and jul3 not in hols:
        out.add(jul3)
    out.add(_nth_weekday(year, 11, 3, 4) + timedelta(days=1))   # day after Thanksgiving
    xeve = date(year, 12, 24)
    if xeve.weekday() < 5 and xeve not in hols:
        out.add(xeve)
    return out


def status(now_utc: datetime | None = None) -> dict:
    """Current market status. Returns:
    {open, session: open|pre|after|closed|holiday|weekend, is_holiday, is_early_close,
     et, label, close_time}."""
    now = (now_utc or datetime.now(timezone.utc)).astimezone(ET)
    d, t = now.date(), now.timetz().replace(tzinfo=None)
    hhmm = now.strftime("%-I:%M %p ET")

    if d.weekday() >= 5:
        return _out(False, "weekend", now, "Market closed · weekend", hhmm)
    if d in nyse_holidays(d.year):
        return _out(False, "holiday", now, "Market closed · holiday", hhmm, is_holiday=True)

    early = d in early_closes(d.year)
    close = _EARLY_CLOSE if early else _CLOSE
    if t < _OPEN:
        return _out(False, "pre", now, f"Pre-market · opens 9:30 AM ET", hhmm, is_early=early, close=close)
    if t >= close:
        return _out(False, "after", now, "Market closed · after hours", hhmm, is_early=early, close=close)
    label = "Market open" + (" · half-day (1:00 PM ET close)" if early else "")
    return _out(True, "open", now, label, hhmm, is_early=early, close=close)


def _last_slot_hour(d: date) -> int:
    """Last :55 slot hour for a date — 12 on half-days (13:00 close), else 15."""
    return 12 if d in early_closes(d.year) else _AGENT_LAST_H


def agent_active(now_utc: datetime | None = None) -> bool:
    """True during the agent's review window on a trading day: 9:55 AM ET → the last
    slot + a 3-min grace (so a :55 tick still fires if a dispatch cycle lands late)."""
    now = (now_utc or datetime.now(timezone.utc)).astimezone(ET)
    d = now.date()
    if d.weekday() >= 5 or d in nyse_holidays(d.year):
        return False
    cur = now.hour * 60 + now.minute
    start = _AGENT_FIRST_H * 60 + _AGENT_MIN                       # 9:55
    end = _last_slot_hour(d) * 60 + _AGENT_MIN + 3                 # last slot + grace
    return start <= cur <= end


def next_agent_slot(now_utc: datetime | None = None) -> datetime:
    """The next :55 review slot strictly after `now` — today's remaining slots, else
    the first slot (9:55) of the next trading day. Returns naive UTC (matches the
    scheduler's clock)."""
    now = (now_utc or datetime.now(timezone.utc)).astimezone(ET)
    d = now.date()
    for _ in range(8):                                            # today + up to a week (holidays)
        if d.weekday() < 5 and d not in nyse_holidays(d.year):
            for h in range(_AGENT_FIRST_H, _last_slot_hour(d) + 1):
                slot = datetime.combine(d, time(h, _AGENT_MIN), tzinfo=ET)
                if slot > now:
                    return slot.astimezone(timezone.utc).replace(tzinfo=None)
        d += timedelta(days=1)
        now = datetime.combine(d, time(0, 0), tzinfo=ET)          # all of the next day's slots qualify
    return (now_utc or datetime.now(timezone.utc)).replace(tzinfo=None) + timedelta(hours=1)


def _out(is_open, session, now, label, hhmm, *, is_holiday=False, is_early=False, close=None) -> dict:
    return {
        "open": is_open, "session": session, "is_holiday": is_holiday,
        "is_early_close": is_early, "et": hhmm, "label": label,
        "close_time": ("1:00 PM ET" if close == _EARLY_CLOSE else "4:00 PM ET") if close else None,
        "as_of": now.isoformat(),
    }
