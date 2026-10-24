#!/usr/bin/env python3
"""Post each event in LatestNews.json to Discord when its start time passes.

Run by .github/workflows/event_starts.yml. The window is (WINDOW_START,
WINDOW_END]: the creation times of the last successful run and of this run.
Consecutive runs tile time with no gap and no overlap, so no state file is
committed. A commit here would also post to Discord as a push.
"""
import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List

import requests

NEWS_FILE = "LatestNews.json"

# Used when no successful run exists yet: the cron interval plus margin.
FIRST_RUN_LOOKBACK = 20 * 60

# After a long outage (GitHub disables idle schedules after 60 days), events
# older than this are history, not news, and are not posted.
MAX_LOOKBACK = 6 * 3600

COLOURS = {"seasonal": 0xE67E22, "broadcast": 0x3498DB}


def _ts(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def started_between(events: List[Dict], after: int, until: int) -> List[Dict]:
    return sorted(
        (e for e in events if e.get("start") and after < e["start"] <= until),
        key=lambda e: e["start"],
    )


def embed(evt: Dict) -> Dict:
    # <t:...> renders in each reader's own time zone, with a countdown.
    if evt.get("endNote"):
        ends = evt["endNote"]
    elif evt.get("end"):
        ends = f"<t:{evt['end']}:F> (<t:{evt['end']}:R>)"
    else:
        ends = "Not announced"

    label = "Broadcast" if evt.get("category") == "broadcast" else "Event"
    return {
        "title": f"{label} started: {evt['title']}",
        "url": evt["url"],
        "color": COLOURS.get(evt.get("category"), 0x95A5A6),
        "fields": [
            {"name": "Started", "value": f"<t:{evt['start']}:F>", "inline": True},
            {"name": "Ends", "value": ends, "inline": True},
        ],
        "footer": {"text": "Lodestone"},
    }


def main() -> int:
    until = _ts(os.environ["WINDOW_END"])
    after = (
        _ts(os.environ["WINDOW_START"])
        if os.environ.get("WINDOW_START")
        else until - FIRST_RUN_LOOKBACK
    )
    after = max(after, until - MAX_LOOKBACK)

    with open(NEWS_FILE, encoding="utf-8") as f:
        events = json.load(f).get("events", [])

    due = started_between(events, after, until)
    print(f"Window {after} → {until}: {len(due)} event(s) started")
    if not due:
        return 0

    webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    dry_run = os.environ.get("DRY_RUN") == "1"
    if not webhook and not dry_run:
        print("::error::DISCORD_WEBHOOK_URL is not set")
        return 1

    # Discord takes at most 10 embeds per message.
    for i in range(0, len(due), 10):
        payload = {"embeds": [embed(e) for e in due[i:i + 10]]}
        if dry_run:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            continue
        r = requests.post(
            webhook,
            json=payload,
            headers={"User-Agent": "DiscordBot (ffxiv-latest-news, 1.0)"},
            timeout=10,
        )
        r.raise_for_status()
        for e in due[i:i + 10]:
            print(f"  ✅ Posted: {e['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
