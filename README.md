# Business Visit — Guangzhou Itinerary Site

A single-file, dependency-free itinerary site built for a business visitor to
Guangzhou. It turns a WhatsApp conversation with a customer into a living,
interactive plan: hotel pick, factory visits, a drag-and-drop weekly schedule
that syncs across devices, a floating minimap with real distances and drive
times, live weather and a pre-trip checklist.

Live at: https://trip.arielzhu.space/nate/

## Structure

```
index.html            landing page
nate/                 the itinerary site
  index.html          the whole app (HTML + CSS + JS, no build step)
  font/               Nunito woff2 subsets
  img/                hotel photos
server/
  trip-plan-sync.py   tiny Python service that persists the plan to plan.json
```

## Runtime files (not in the repo)

- `nate/plan.json` — written by `trip-plan-sync.py` on every plan change
  (revision-bumped). The page polls it to keep multiple devices in sync.
- `nate/weather.json` — refreshed daily by a cron job; the page reads it on
  the same origin so no external request is made (important inside China).
  Shape: `{"fetched": iso, "now": {t, rh, code}, "trip": [{d, hi, lo, rain, code}]}`

## How the plan API works

`server/trip-plan-sync.py` serves exactly one tiny JSON document:

- `GET /nate/api/plan` → `{"plan": [[...] × 5 days], "rev": N}`
- `PUT /nate/api/plan` → validates keys, capacity and duplicates, bumps `rev`
  and atomically writes `plan.json`.

Run it on the host (here `python3 /usr/local/bin/trip-plan-sync.py`), bind to
an interface Caddy can reach, and reverse-proxy `/nate/api/*` to it.

## Caddy example

```
trip.arielzhu.space {
    encode zstd gzip

    handle /nate/api/* {
        uri strip_prefix /nate/api
        reverse_proxy 172.19.0.1:8791
    }

    handle {
        root * /data/trip
        file_server
        header {
            Cache-Control "no-cache"
            X-Content-Type-Options "nosniff"
            Referrer-Policy "no-referrer"
        }
    }
}
```

## Content

The places, hotels and distances are hardcoded in `nate/index.html` (the `P`,
`VISITS`, `PROPS`, `DAYS` objects) — tune those for your own trip. Phone and
booking links are per-visit too.
