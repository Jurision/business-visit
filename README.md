# China Journey Planner

A dependency-free personal journey page for a 2026 Guangzhou → Qingdao →
Yantai night ferry → Dalian → Xingan → Nanchang → Guangzhou trip.

Live at: https://trip.arielzhu.space/travel/

## Current behavior

- The default itinerary runs for 12 calendar days, from 12 to 23 October 2026.
- Dalian and the Yantai night ferry are fixed parts of the route.
- Qingdao, Dalian, Xingan and Nanchang stays can be adjusted directly.
- Dates, weekdays, accommodation nights and the budget recalculate together.
- A visible warning appears above the 14-day upper limit; transport time is not
  silently compressed.
- Public content omits private family addresses and marks schedules, fares and
  availability as reference information that must be rechecked.

## Structure

```text
index.html             existing site index; intentionally unchanged
travel/                current public journey page
  index.html           page, styles, data and interactions
  favicon.svg
  img/
    personal-trip-watercolor.png
nate/index.html        legacy client-side redirect to /travel/
scripts/verify-live.sh compares deployed HTML with travel/index.html
server/                legacy schedule-sync service retained for history
tests/                 dependency-free contract and legacy API tests
```

## Validation

```sh
python3 -m unittest discover -s tests -v
sh scripts/verify-live.sh
```

The production Caddy route serves `/travel/` from its own directory, redirects
the old `/nate/` URL to `/travel/`, and leaves the site root unchanged.
