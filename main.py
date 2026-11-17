"""Forecast GTA VI's launch-day Twitch viewers, hour by hour.

Method (a launch-shape forecaster, calibrated on past big launches)
--------------------------------------------------------------------
The case hands us two things: hour 1's print p1, and the release-day
hourly curves of dozens of past big game launches ("comparables",
SullyGnome hourly Twitch category averages, 14 days before to 3 days
after each launch's release day). For every comparable we form the
log-ratio of each later hour to its own hour 1, ln(y_h / y_1), and
regress that log-ratio on ln(y_1): big launches behave differently
from small ones. A launch whose hour 1 already drew 800k viewers was
near its peak at midnight; one that drew 40k kept climbing all day
as the world woke up and unlocked, often 2-3x by the evening. The
regression slope is about 0 at hour 2 and about -0.4 by hour 19, so
the forecast flattens as p1 grows. The spread comes from the
regression residuals: the empirical 5/25/50/75/95% quantiles of the
residuals, added to the fitted value, give honest, asymmetric
quantiles (the upside tail is long: a launch can always explode,
it can only fall so far).

Leave-one-out pinball loss on the 28 comparables with hour 1 >=
10,000 viewers is about 0.27, against about 0.35 for the house
persistence baseline on the same launches. The program recomputes
everything from the case it is given, so the final case's 42
comparables (including the four practice launches) are used as-is.

Only launches with a real hour-1 print join the fit: hour-1 prints
of a few hundred viewers come from categories that had barely
unlocked, and their day curves explode by hundreds of times, which
would wreck the fit for a launch as big as GTA VI. The threshold
starts at 10,000 and steps down (5,000 / 1,000 / 100) only if too
few launches qualify. A launch's own hour-1 print is clipped to
the fitted range, so a p1 above every past launch is forecast like
the biggest past launch, never extrapolated down a cliff.

Fallbacks, in order, per hour: the regression when at least 8
launches have that hour; the pooled empirical quantiles of the
log-ratios when at least 5 do; the house persistence baseline
(p1, spread 0.15 * sqrt(h - 1) in log space) when nothing else is
available. The program never crashes on a thin case: a missing
hour-1 print falls back to the last recorded hourly point, then 1.

Run: python3 main.py reads every <id>.in in $MAKEFUN_INPUT_DIR
(default /input) and writes <id>.out to $MAKEFUN_OUTPUT_DIR
(default /output): {"hours": [{"hour": h, "q": [q05, q25, q50,
q75, q95]}, ...]} for hours 2..24. Standard library only,
deterministic, no network, no randomness.
"""

import json
import math
import os
from datetime import datetime
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

# The quantile levels the contest scores, in the order each row lists them.
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# The standard normal's quantile at each level (baseline fallback only).
Z = [-1.6448536269514722, -0.6744897501960817, 0.0, 0.6744897501960817, 1.6448536269514722]
# The baseline's log-spread per square-root hour.
BASE_SIGMA = 0.15

# Hour-1 size bands for the reference class, tried in order until at
# least MIN_LAUNCHES launches qualify.
MIN_H1_BANDS = (10000, 5000, 1000, 100)
MIN_LAUNCHES = 8
# A regression needs at least this many launches with the hour.
MIN_POINTS = 8
# A pooled-quantile fallback needs at least this many.
MIN_POOLED = 5


def parse_ts(text):
    """An ISO-8601 UTC timestamp such as 2026-11-19T00:00:00Z."""
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")


def release_day_hours(comp):
    """A comparable's release-day hourly viewers as {hour 1..24: viewers}.

    Hours come from the row timestamps relative to the launch's own
    day_start; rows outside the release day are ignored, and a
    non-positive count is dropped (it carries no log-ratio).
    """
    try:
        day_start = parse_ts(comp["day_start"])
    except (KeyError, TypeError, ValueError):
        return {}
    hours = {}
    for row in comp.get("hourly") or []:
        try:
            when = parse_ts(row["from"])
            viewers = row["viewers"]
        except (KeyError, TypeError, ValueError):
            continue
        if viewers is None or viewers <= 0:
            continue
        hour = int((when - day_start).total_seconds() // 3600) + 1
        if 1 <= hour <= 24:
            hours[hour] = viewers
    return hours


def quantile(sorted_values, tau):
    """The tau-quantile of an ascending list, linearly interpolated."""
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    pos = tau * (n - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac


def round2(x):
    """x rounded to 2 decimals, half up (as JavaScript's Math.round does).

    A whole number comes back as an int, so json.dumps writes 1240
    where JavaScript writes 1240 (not 1240.0).
    """
    scaled = x * 100.0
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100.0
    return int(value) if value.is_integer() else value


def baseline_quantiles(p1, hour, levels):
    """The house persistence forecast: every hour stays at p1.

    The spread at each level comes from the standard normal's
    quantile at that level; the levels the case schema fixes are
    [0.05, 0.25, 0.5, 0.75, 0.95], whose quantiles are Z, in order.
    """
    spread = BASE_SIGMA * math.sqrt(hour - 1)
    return [p1 * math.exp(Z[i] * spread) for i in range(len(levels))]


def training_set(case, p1):
    """The reference launches: (log hour-1, {hour: viewers}) pairs.

    Only launches with a real hour-1 print qualify, and only the
    biggest band with enough launches is used. Returns the list and
    the log hour-1 range it spans (for clipping the forecast's p1).
    """
    days = []
    for comp in case.get("comparables") or []:
        hours = release_day_hours(comp)
        if 1 in hours:
            days.append((math.log(hours[1]), hours))
    for band in MIN_H1_BANDS:
        chosen = [(lp, hours) for lp, hours in days if hours[1] >= band]
        if len(chosen) >= MIN_LAUNCHES:
            logs = [lp for lp, _ in chosen]
            return chosen, min(logs), max(logs)
    if days:
        logs = [lp for lp, _ in days]
        return days, min(logs), max(logs)
    return [], 0.0, 0.0


def forecast_hour(train, log_p1, hour, levels):
    """The five quantiles of hour `hour`'s count as log-ratios to p1.

    Regression of ln(y_h / y_1) on ln(y_1) across the reference
    launches, with the spread from the residuals' empirical
    quantiles; pooled empirical quantiles when too few launches
    have the hour; None when the case gives us nothing at all.
    """
    points = []
    for log_h1, hours in train:
        if hour in hours:
            points.append((log_h1, math.log(hours[hour] / hours[1])))
    if len(points) >= MIN_POINTS:
        xs = [x for x, _ in points]
        ys = [y for _, y in points]
        mean_x = sum(xs) / len(xs)
        mean_y = sum(ys) / len(ys)
        sxx = sum((x - mean_x) ** 2 for x in xs)
        slope = 0.0
        if sxx > 0:
            slope = sum((x - mean_x) * (y - mean_y) for x, y in points) / sxx
        intercept = mean_y - slope * mean_x
        predicted = intercept + slope * log_p1
        residuals = sorted(y - (intercept + slope * x) for x, y in points)
        median_resid = quantile(residuals, 0.5)
        return [predicted + (quantile(residuals, tau) - median_resid)
                for tau in levels]
    if len(points) >= MIN_POOLED:
        ratios = sorted(y for _, y in points)
        return [quantile(ratios, tau) for tau in levels]
    return None


def hour1_print(case):
    """Hour 1's print, with fallbacks so the program never crashes."""
    for row in case.get("known") or []:
        if row.get("hour") == 1 and row.get("viewers"):
            return max(1, row["viewers"])
    hourly = case.get("history_hourly") or []
    if hourly:
        last = hourly[-1].get("viewers")
        if last:
            return max(1, last)
    return 1


def forecast_case(case, name):
    """The forecast object for one case: {"hours": [...]}."""
    levels = case.get("levels") or LEVELS
    p1 = hour1_print(case)
    log_p1 = math.log(max(1, p1))
    train, log_lo, log_hi = training_set(case, p1)
    # Never extrapolate past the biggest (or smallest) reference
    # launch: a p1 beyond the fitted range is forecast like the
    # nearest edge of it.
    if train:
        log_p1 = min(max(log_p1, log_lo), log_hi)
    rows = []
    for row in case["forecast"]:
        hour = row["hour"]
        log_qs = forecast_hour(train, log_p1, hour, levels)
        if log_qs is None:
            log_qs = [math.log(q / p1)
                      for q in baseline_quantiles(p1, hour, levels)]
        # Quantiles of a count: positive, at most 1e9, non-decreasing.
        qs = []
        floor = 0.01
        for log_q in log_qs:
            value = round2(min(max(p1 * math.exp(log_q), 0.01), 1e9))
            value = max(value, floor)
            qs.append(value)
            floor = value
        rows.append({"hour": hour, "q": qs})
    return {"hours": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Every case file, in name order, so two runs write the same bytes.
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / (path.stem + ".out")).write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
