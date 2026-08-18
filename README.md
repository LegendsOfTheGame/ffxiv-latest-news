# FFXIV Latest News API

Automated JSON API providing FFXIV maintenance schedules and seasonal events.

## 📡 API Endpoint

```
https://raw.githubusercontent.com/LegendsOfTheGame/ffxiv-latest-news/main/LatestNews.json
```

## 📋 Response Format

```json
{
  "version": "2.0.0",
  "lastUpdated": 1739692800,
  "source": "lodestonenews.com",
  "maintenance": {
    "title": "All Worlds Maintenance (Feb. 16)",
    "start": 1739692800,
    "end": 1739703600,
    "url": "https://na.finalfantasyxiv.com/lodestone/news/detail/..."
  },
  "events": [
    {
      "title": "Valentione's Day (2026)",
      "category": "seasonal",
      "start": 1738483200,
      "end": 1739692740,
      "url": "https://na.finalfantasyxiv.com/lodestone/topics/detail/...",
      "description": "The season of ardor and affection..."
    }
  ]
}
```

### Fields

- **version** (string): API format version
- **lastUpdated** (number): UNIX timestamp of last update (UTC)
- **source** (string): Data source attribution
- **maintenance** (object|null): Next scheduled maintenance, or null if none
  - **maintenance.title** (string): Maintenance title
  - **maintenance.start** (number): Start time (UNIX timestamp, UTC)
  - **maintenance.end** (number): End time (UNIX timestamp, UTC)
  - **maintenance.url** (string): Lodestone announcement URL
- **events** (array): Active and upcoming seasonal events
  - **events[].title** (string): Event title
  - **events[].category** (string): "seasonal" or "event"
  - **events[].start** (number): Start time (UNIX timestamp, UTC)
  - **events[].end** (number): End time (UNIX timestamp, UTC)
  - **events[].url** (string): Lodestone event page URL
  - **events[].description** (string): Brief description (max 150 chars)

## 🔄 Update Schedule

- **Every 6 hours** via GitHub Actions
- Fetches from [lodestonenews.com](https://lodestonenews.com) API
- Follows "Read on" links to scrape actual event dates from Lodestone special pages
- Automatically removes expired events

## 🚀 Usage Examples

### JavaScript

```javascript
fetch('https://raw.githubusercontent.com/LegendsOfTheGame/ffxiv-latest-news/main/LatestNews.json')
  .then(res => res.json())
  .then(data => {
    if (data.maintenance) {
      const start = new Date(data.maintenance.start * 1000);
      const end = new Date(data.maintenance.end * 1000);
      console.log(`Maintenance: ${data.maintenance.title}`);
      console.log(`${start.toLocaleString()} - ${end.toLocaleString()}`);
    }

    data.events.forEach(event => {
      const endDate = new Date(event.end * 1000);
      console.log(`${event.title} - ends ${endDate.toLocaleDateString()}`);
    });
  });
```

### Python

```python
import requests
from datetime import datetime

response = requests.get(
    'https://raw.githubusercontent.com/LegendsOfTheGame/ffxiv-latest-news/main/LatestNews.json'
)
data = response.json()

if data['maintenance']:
    start = datetime.fromtimestamp(data['maintenance']['start'])
    end = datetime.fromtimestamp(data['maintenance']['end'])
    print(f"Maintenance: {data['maintenance']['title']}")
    print(f"{start} - {end}")

for event in data['events']:
    end_date = datetime.fromtimestamp(event['end'])
    print(f"{event['title']} - ends {end_date.strftime('%B %d, %Y')}")
```

### C# (.NET)

```csharp
using System.Net.Http;
using System.Text.Json;

var client = new HttpClient();
var json = await client.GetStringAsync(
    "https://raw.githubusercontent.com/LegendsOfTheGame/ffxiv-latest-news/main/LatestNews.json"
);

using var doc = JsonDocument.Parse(json);
var root = doc.RootElement;

// Check maintenance
if (root.GetProperty("maintenance").ValueKind != JsonValueKind.Null)
{
    var maintenance = root.GetProperty("maintenance");
    var title = maintenance.GetProperty("title").GetString();
    var start = DateTimeOffset.FromUnixTimeSeconds(
        maintenance.GetProperty("start").GetInt64()
    );
    var end = DateTimeOffset.FromUnixTimeSeconds(
        maintenance.GetProperty("end").GetInt64()
    );
    Console.WriteLine($"Maintenance: {title}");
    Console.WriteLine($"{start} - {end}");
}

// List events
foreach (var eventItem in root.GetProperty("events").EnumerateArray())
{
    var title = eventItem.GetProperty("title").GetString();
    var endTs = eventItem.GetProperty("end").GetInt64();
    var endDate = DateTimeOffset.FromUnixTimeSeconds(endTs);
    Console.WriteLine($"{title} - ends {endDate:MMMM dd, yyyy}");
}
```

## 🛠️ How It Works

1. **GitHub Actions** runs `parse_news.py` every 6 hours
2. Script fetches from lodestonenews.com Topics and Maintenance APIs
3. For seasonal events:
   - Detects events by keywords (Valentione's, Heavensturn, etc.)
   - Follows "Read on" redirect links (`sqex.to` → actual event page)
   - Scrapes event dates from Lodestone special pages
   - Filters out expired events
4. Commits `LatestNews.json` to repository
5. Available immediately via GitHub raw URL

## 📅 Supported Events

- Valentione's Day
- Heavensturn
- Little Ladies' Day
- Hatching-tide
- Make It Rain Campaign
- Moonfire Faire
- The Rising
- All Saints' Wake
- Starlight Celebration
- Moogle Treasure Trove
- Irregular Tomestones campaigns

## 🎣 Ocean Fishing Bait

A second, unrelated dataset served from the same repository.

```
https://raw.githubusercontent.com/LegendsOfTheGame/ffxiv-latest-news/main/OceanBait.json
```

For each Ocean Fishing zone: the fish that triggers a spectral current, and the
bait that catches it. The game's own `IKD*` sheets carry the voyage schedule, the
stops and the objectives, but hold nothing about bait — that part is community
measurement.

```json
{
  "source": "https://github.com/NotNite/DistantSeas",
  "licence": "AGPL-3.0",
  "built": "2026-08-18T17:46:52Z",
  "routes": {
    "ruby": {
      "KuganeCoast": {
        "fish": "Spectral Wrasse",
        "fishId": 40549,
        "bait": "Ragworm",
        "baitId": 29714,
        "alsoFlagged": ["Krill"],
        "verifiedInGame": "2026-08-18"
      }
    }
  }
}
```

### Fields

- **bait** / **baitId**: one bait per zone. Where the source flags more than one,
  the cheapest is chosen and the rest listed in `alsoFlagged`.
- **verifiedInGame**: present only where the trigger fish was actually landed on
  the listed bait, in game, on that date. Absent means derived but unconfirmed.

Bite times are **deliberately excluded**. They are tuning values that move on
patches and hotfixes, and a periodically refreshed file would present stale ones
as current.

This file is **not** touched by the scheduled workflow, which stages only
`LatestNews.json`. It is regenerated occasionally — monthly is plenty — by
`tools/Build-OceanBait.py` in the Time Memoria repository.

## 🤝 Credits

- **Data Source**: [Lodestone News](https://lodestonenews.com) by [@MattAntonelli](https://github.com/mattantonelli)
- **Ocean Fishing Bait**: derived from [Distant Seas](https://github.com/NotNite/DistantSeas) by [@NotNite](https://github.com/NotNite), used under AGPL-3.0
- **Built For**: 
  - [XIVToDo](https://xivtodo.com) - FFXIV task tracker
  - [Time Memoria v2](https://github.com/LegendsOfTheGame/TimeMemoriaV2) - FFXIV Dalamud plugin

## 📜 License

This project is open source. Data is aggregated from official Square Enix Lodestone announcements.

## 🐛 Issues & Contributions

Found a bug or want to add support for more event types? Open an issue or PR!
