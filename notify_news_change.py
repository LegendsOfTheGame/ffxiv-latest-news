#!/usr/bin/env python3
"""Post a Discord summary when LatestNews.json changes in more than lastUpdated.

Run by .github/workflows/update_news.yml after its commit. Every run still
commits the new lastUpdated, because readers check how often the file
changes; this script keeps those timestamp-only commits out of Discord.

Usage: notify_news_change.py OLD.json NEW.json
"""
import json
import os
import sys
from typing import Dict, List, Optional

import requests


def _load(path: str) -> Dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _key(evt: Dict) -> tuple:
    return (evt.get("title"), evt.get("start"), evt.get("end"))


def _when(evt: Optional[Dict]) -> str:
    if not evt or not evt.get("start"):
        return ""
    return f" (<t:{evt['start']}:F>)"


def changes(old: Dict, new: Dict) -> List[str]:
    lines: List[str] = []

    old_events = {_key(e): e for e in old.get("events", [])}
    new_events = {_key(e): e for e in new.get("events", [])}
    for k, e in new_events.items():
        if k not in old_events:
            lines.append(f"➕ New: [{e['title']}]({e['url']}){_when(e)}")
    for k, e in old_events.items():
        if k not in new_events:
            lines.append(f"➖ Ended or removed: {e['title']}")

    old_m, new_m = old.get("maintenance"), new.get("maintenance")
    if new_m and new_m != old_m:
        lines.append(f"🔧 Maintenance: [{new_m['title']}]({new_m['url']}){_when(new_m)}")
    elif old_m and not new_m and (new.get("lastMaintenance") or {}).get("title") == old_m["title"]:
        # Checked against lastMaintenance: a failed fetch also empties
        # "maintenance", and that is not the maintenance ending.
        lines.append(f"🔧 Maintenance over: {old_m['title']}")

    # A record going to null is ageing out or a failed fetch, not news.
    for field, label in (("lastEvent", "🏁 Last event"), ("lastMaintenance", "🔧 Last maintenance")):
        was, now = old.get(field), new.get(field)
        if now and now != was:
            lines.append(f"{label}: [{now['title']}]({now['url']})")

    # Any other field that moved, so a real change always has a line.
    if not lines:
        skip = {"lastUpdated", "events", "maintenance", "lastEvent", "lastMaintenance"}
        moved = sorted(
            k for k in set(old) | set(new)
            if k not in skip and old.get(k) != new.get(k)
        )
        if moved:
            lines.append("Changed: " + ", ".join(f"`{k}`" for k in moved))
    return lines


def main() -> int:
    old, new = _load(sys.argv[1]), _load(sys.argv[2])
    strip = lambda d: {k: v for k, v in d.items() if k != "lastUpdated"}
    if strip(old) == strip(new):
        print("Only lastUpdated changed; nothing posted")
        return 0

    lines = changes(old, new)
    if not lines:
        print("Only records cleared; nothing posted")
        return 0

    payload = {"embeds": [{
        "title": "FFXIV news updated",
        "url": "https://github.com/LegendsOfTheGame/ffxiv-latest-news/blob/main/LatestNews.json",
        "description": "\n".join(lines)[:4000],
        "color": 0x9B59B6,
        "footer": {"text": "Lodestone"},
    }]}

    if os.environ.get("DRY_RUN") == "1":
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook:
        # The data is already committed; a missing secret must not fail the run.
        print("::warning::DISCORD_WEBHOOK_URL is not set; change not posted")
        return 0

    r = requests.post(
        webhook,
        json=payload,
        headers={"User-Agent": "DiscordBot (ffxiv-latest-news, 1.0)"},
        timeout=10,
    )
    r.raise_for_status()
    print(f"  ✅ Posted {len(lines)} change(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
