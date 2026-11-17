# gta6-twitch-ccu-forecast-01

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/labixiaoge/gta6-twitch-ccu-forecast-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/labixiaoge/gta6-twitch-ccu-forecast-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

<!-- NOTE TO THE SUBMITTER: replace {owner} with labixiaoge and {repo}
     with this repository's name in the two badge URLs above, and
     {referral_code} in the footer below, before submitting. -->

Forecast GTA VI's launch-day Twitch viewers hour by hour: a program
that reads one case (everything recorded up to the end of the release
day's first hour, that hour's print included) and writes, for each of
hours 2 to 24, five quantiles (5%, 25%, 50%, 75%, 95%) of that hour's
concurrent-viewer count.

## About

Grand Theft Auto VI releases on 19 November 2026 on PlayStation 5 and
Xbox Series X|S, and no console maker publishes a player count. This
entry forecasts the next best thing, Twitch's own count of concurrent
viewers in the "Grand Theft Auto VI" category, from its first hour's
print alone.

The method is a launch-shape forecaster calibrated on past big game
launches. The case carries the release-day hourly curves of dozens of
past launches (SullyGnome hourly Twitch category averages). For every
comparable launch the program forms the log-ratio of each later hour
to its own hour 1 and regresses that log-ratio on the log of hour 1:
big launches behave differently from small ones — a launch whose
hour 1 already drew 800k viewers was near its peak at midnight,
while one that drew 40k kept climbing all day as the world woke up
and unlocked, often 2–3x by the evening. The spread comes from the
regression residuals' empirical quantiles, so the forecast is honest
about the long upside tail. Only launches with a real hour-1 print
(10,000 viewers or more, stepping down only if too few qualify) join
the fit, and hour 1 is clipped to the fitted range, so a print above
every past launch is forecast like the biggest past launch, never
extrapolated down a cliff. Leave-one-out pinball loss on the 28
comparables with hour 1 >= 10,000 is about 0.27, against about 0.35
for the house persistence baseline on the same launches. Per-hour
fallbacks: pooled empirical quantiles, then the house baseline.
Standard library only, deterministic, no network, no randomness,
about 0.15 s per case.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

`main.py` reads every `<id>.in` in the input directory and writes
`<id>.out` to the output directory: `{"hours": [{"hour": h, "q":
[q05, q25, q50, q75, q95]}, ...]}` for hours 2 to 24.

---

<sub>Entered on [make.fun](https://make.fun/?ref=j11gmnzr&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
