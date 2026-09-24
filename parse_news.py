#!/usr/bin/env python3
import html
import json
import requests
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Dict, List

# --- Configuration ---
LODESTONE_API = "https://lodestonenews.com/news"
LODESTONE_BASE = "https://na.finalfantasyxiv.com"
OUTPUT_FILE = "LatestNews.json"
RETENTION_DAYS = 30

SEASONAL_KEYWORDS = [
    "Valentione", "Heavensturn", "Little Ladies", "Hatching",
    "Make It Rain", "Moonfire", "The Rising", "All Saints",
    "Starlight", "Moogle Treasure", "Irregular Tomestone",
    "Collaboration Event", "Yo-kai"
]

# Front-page banners that link to /lodestone/special/ but are permanent pages,
# not events. Anything else without a date range is skipped anyway; this only
# saves the requests.
SPECIAL_SKIP = ("fankit", "friend_recruit", "patchnote_log", "update_log")

# "Tuesday, August 4, 2026 at 1:00 a.m. to Monday, October 5, 2026 at 7:59 a.m. (PDT)"
# The start zone is optional (Hatching-tide omits it), and the space before
# "to" is too (Yo-kai 2026 prints "a.m.to").
DATE_RANGE = re.compile(
    r"\w+day,\s+(\w+\s+\d+,\s+\d{4})\s+at\s+(\d+:\d+)\s*([ap]\.m\.)"
    r"(?:\s*\((\w+)\))?"
    r"\s*to\s+\w+day,\s+(\w+\s+\d+,\s+\d{4})\s+at\s+(\d+:\d+)\s*([ap]\.m\.)"
    r"\s*\((\w+)\)",
    re.IGNORECASE,
)


def fetch_api(category: str) -> List[Dict]:
    try:
        url = f"{LODESTONE_API}/{category}"
        print(f"📡 Fetching {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f" ✗ Error fetching {category}: {e}")
        return []


def scrape_event_dates(url: str) -> Tuple[Optional[int], Optional[int]]:
    try:
        print(f"    🌐 Initial URL: {url}")

        # Read dates from whichever page has them first. Most events print
        # them on the special page, but some (FFXV 2026) print them only in
        # the topic body, so every hop is checked before following it on.
        for hop in range(3):
            response = requests.get(url, timeout=15, allow_redirects=True)
            response.raise_for_status()
            content = response.text
            url = response.url

            start, end = find_event_dates(content)
            if start and end:
                print(f"    ✅ Dates found (hop {hop}): {url}")
                return start, end

            if "/lodestone/special/" in url:
                print(f"    ✗ Special page has no date range: {url}")
                return None, None

            # Direct special-page link in the HTML
            special_match = re.search(
                r'href="(https://[^"]*finalfantasyxiv\.com/lodestone/special/[^"]+)"',
                content,
            )
            if special_match:
                url = special_match.group(1)
                print(f"    🔗 Hop {hop + 1}: Direct special link → {url}")
                continue

            # "Read on" link (sqex.to or direct)
            read_on_href = re.search(
                r'href="(https://(?:sqex\.to|[^"]*finalfantasyxiv\.com)/[^"]+)"[^>]*>[^<]*[Rr]ead\s+on',
                content,
            )
            if not read_on_href:
                read_on_href = re.search(
                    r"[Rr]ead\s+on[^<]*<[^>]+href=\"([^\"]+)\"",
                    content,
                )
            if not read_on_href:
                read_on_href = re.search(
                    r'href="(https://sqex\.to/[^"]+)"',
                    content,
                )

            if read_on_href:
                url = read_on_href.group(1)
                print(f"    🔗 Hop {hop + 1}: Read on link → {url}")
                continue

            print(f"    ⚠️ Hop {hop + 1}: No onward link found at {url}")
            break

        print("    ✗ No date range found")
        return None, None

    except Exception as e:
        print(f"    ✗ Scrape error: {e}")
        return None, None


def find_event_dates(content: str) -> Tuple[Optional[int], Optional[int]]:
    """First date range on the page. The visible text wins over the meta
    description: SE has reused an old special page's meta unchanged before
    (Feb 2026 still said 2019), so the meta is only a fallback for a page whose
    body has no range at all. Tags are stripped because the body splits the
    range across <span>s and <br>s."""
    body = re.sub(r"<head>.*?</head>", " ", content, flags=re.DOTALL | re.IGNORECASE)
    body = html.unescape(re.sub(r"<[^>]+>", " ", body))
    match = DATE_RANGE.search(body)

    if not match:
        meta = re.search(r'<meta name="description" content="([^"]*)"', content)
        match = DATE_RANGE.search(html.unescape(meta.group(1))) if meta else None
        if match:
            print("    ⚠️ Body has no date range; falling back to meta description")

    if not match:
        return None, None

    try:
        (
            start_date,
            start_time,
            start_mer,
            start_tz,
            end_date,
            end_time,
            end_mer,
            end_tz,
        ) = match.groups()

        # Normalize AM/PM
        start_mer = start_mer.replace(".", "").upper()
        end_mer = end_mer.replace(".", "").upper()

        # If start timezone is missing (Hatching-tide), assume same as end
        if not start_tz:
            start_tz = end_tz

        tz_map = {"PST": 8, "PDT": 7, "EST": 5, "EDT": 4}
        s_offset = tz_map.get(start_tz.upper(), 8)
        e_offset = tz_map.get(end_tz.upper(), 8)

        # Parse as UTC-naive, then treat as UTC and shift by offset
        s_dt = datetime.strptime(
            f"{start_date} {start_time} {start_mer}",
            "%B %d, %Y %I:%M %p",
        ).replace(tzinfo=timezone.utc)
        e_dt = datetime.strptime(
            f"{end_date} {end_time} {end_mer}",
            "%B %d, %Y %I:%M %p",
        ).replace(tzinfo=timezone.utc)

        s_ts = int((s_dt + timedelta(hours=s_offset)).timestamp())
        e_ts = int((e_dt + timedelta(hours=e_offset)).timestamp())

        print(
            f"    ✅ Parsed: {start_date} ({start_tz}) → "
            f"{end_date} ({end_tz})"
        )
        return s_ts, e_ts

    except ValueError as e:
        print(f"    ✗ Date parse error: {e}")
        return None, None


def page_title(content: str) -> Optional[str]:
    """Event name from a special page's <title>, without the site suffix or
    the trailing year: "Yo-kai Watch: Gather One, Gather All! 2026"."""
    match = re.search(r"<title>([^<]*)</title>", content)
    if not match:
        return None
    title = html.unescape(match.group(1)).split(" | ")[0].strip()
    return re.sub(r"\s+\d{4}$", "", title) or None


def fetch_banner_events() -> List[Dict]:
    """Events linked from the Lodestone front-page banners.

    The topics API returns only the latest 20 topics, so an event announced
    weeks before it ends (Yo-kai Watch 2026, announced in early August) drops
    out of it while still running. The front page keeps a banner up for as
    long as the event runs."""
    try:
        response = requests.get(f"{LODESTONE_BASE}/lodestone/", timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f" ✗ Error fetching Lodestone front page: {e}")
        return []

    paths = []
    for path in re.findall(r'href="(/lodestone/special/[^"?#]+)', response.text):
        slug = path[len("/lodestone/special/"):]
        if slug.startswith(SPECIAL_SKIP) or path in paths:
            continue
        paths.append(path)

    events: List[Dict] = []
    for path in paths:
        url = LODESTONE_BASE + path
        print(f"  📅 Checking banner: {url}")
        try:
            page = requests.get(url, timeout=15)
            page.raise_for_status()
        except Exception as e:
            print(f"    ✗ Fetch error: {e}")
            continue

        start, end = find_event_dates(page.text)
        title = page_title(page.text)
        if not start or not end or not title:
            print("    ⚠️ Skipping — no date range or title")
            continue

        events.append({
            "title": title,
            "start": start,
            "end": end,
            "url": url,
            "category": "seasonal",
        })
        print(f"    ✅ {title}")

    return events


def parse_maintenance(
    maint_list: List[Dict], now: int
) -> Tuple[Optional[Dict], Optional[Dict]]:
    current, last = None, None

    for item in maint_list:
        if "All Worlds Maintenance" not in item.get("title", ""):
            continue

        try:
            start_ts = int(
                datetime.fromisoformat(
                    item["start"].replace("Z", "+00:00")
                ).timestamp()
            )
            end_ts = int(
                datetime.fromisoformat(
                    item["end"].replace("Z", "+00:00")
                ).timestamp()
            )
            pub_ts = int(
                datetime.fromisoformat(
                    item["time"].replace("Z", "+00:00")
                ).timestamp()
            )

            m_data = {
                "title": item["title"],
                "start": start_ts,
                "end": end_ts,
                "pub": pub_ts,
                "url": item["url"],
            }

            if end_ts > now:
                if not current or pub_ts > current["pub"]:
                    current = m_data
            else:
                if not last or pub_ts > last["pub"]:
                    last = m_data

        except Exception as e:
            print(
                f" ✗ Maintenance parse error for '{item.get('title', '')}': {e}"
            )
            continue

    if current:
        current = {k: v for k, v in current.items() if k != "pub"}
    if last:
        last = {k: v for k, v in last.items() if k != "pub"}

    return current, last


def main() -> None:
    print("=" * 60)
    print("FFXIV Latest News Updater v2.0.0")
    print("=" * 60)

    now = int(datetime.now(timezone.utc).timestamp())

    topics = fetch_api("topics")
    maint_list = fetch_api("maintenance")

    print("\n🔧 Processing Maintenance...")
    current_maint, last_maint = parse_maintenance(maint_list, now)
    if current_maint:
        print(f"  ✅ Current: {current_maint['title']}")
    else:
        print("  ℹ️ No upcoming maintenance found")
    if last_maint:
        print(f"  ✅ Last: {last_maint['title']}")

    print("\n🎉 Processing Events...")
    events: List[Dict] = []
    last_event: Optional[Dict] = None
    cutoff = now - (RETENTION_DAYS * 86400)

    # Keyed on the date range, so an event found both as a topic and as a
    # banner is listed once. The banner is added second and wins: its title
    # is the event's name ("Yo-kai Watch: Gather One, Gather All!"), where the
    # topic title is an announcement ("... Collaboration Event Returns!").
    found: Dict[Tuple[int, int], Dict] = {}

    for item in topics:
        title = item.get("title", "")
        if not any(kw.lower() in title.lower() for kw in SEASONAL_KEYWORDS):
            continue

        print(f"  📅 Checking: {title}")
        start, end = scrape_event_dates(item["url"])

        if not start or not end:
            print("    ⚠️ Skipping — could not parse dates")
            continue

        found[(start, end)] = {
            "title": title,
            "start": start,
            "end": end,
            "url": item["url"],
            "category": "seasonal",
        }

    for evt in fetch_banner_events():
        found[(evt["start"], evt["end"])] = evt

    for evt in found.values():
        end = evt["end"]
        if end > now:
            events.append(evt)
            print("    ✅ Active event added")
        elif end > cutoff:
            if not last_event or end > last_event["end"]:
                last_event = evt
                print("    ✅ Stored as lastEvent")

    output = {
        "version": "2.0.0",
        "lastUpdated": now,
        "source": "lodestonenews.com",
        "maintenance": current_maint,
        "lastMaintenance": last_maint,
        "events": sorted(events, key=lambda x: x["start"]),
        "lastEvent": last_event,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Wrote {OUTPUT_FILE}")
    print(f"   Events active: {len(events)}")
    print(f"   Maintenance: {'Yes' if current_maint else 'None'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
