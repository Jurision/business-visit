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
scripts/
  verify-live.sh      confirms the deployed HTML exactly matches the checkout
tests/                dependency-free validation and API unit tests
```

## Runtime files (not in the repo)

- `nate/plan.json` — written by `trip-plan-sync.py` on every plan change
  (revision-bumped). The page polls it to keep multiple devices in sync.
- `nate/weather.json` — refreshed daily by a cron job; the page reads it on
  the same origin so no external request is made (important inside China).
  Shape: `{"fetched": iso, "now": {t, rh, code}, "trip": [{d, hi, lo, rain, code}]}`

## How the plan API works

`server/trip-plan-sync.py` serves exactly one tiny JSON document:

- `GET /nate/api/plan` → `{"plan": [[...] × 5 days], "check": {"c1": true, ...}, "rev": N}`
- `PUT /nate/api/plan` → accepts `plan` and/or `check` (each optional, validated
  separately); fields merge independently so editing the schedule on one device
  never clobbers checklist state from another. Bumps `rev` and atomically writes
  `plan.json`.

Both the schedule and the pre-departure checklist sync across devices this way.
The page polls every 8s and also pushes each change (debounced) after edits.

The service validates a complete plan: every known visit must occur exactly
once, no day may contain more than three visits, and checklist keys are
allow-listed. The store path, bind host and port can be overridden with
`TRIP_PLAN_STORE`, `TRIP_PLAN_HOST` and `TRIP_PLAN_PORT` for testing.

## Public access

The `/nate` page and its sync API are intentionally public and do not require
a username or password. `robots.txt` and the page's `noindex` metadata reduce
accidental search-engine discovery, but they are not access control. Because
`PUT /nate/api/plan` is also public, deploy only itinerary information that is
appropriate for anyone with the URL to view and edit.

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
            Strict-Transport-Security "max-age=31536000; includeSubDomains"
            Content-Security-Policy "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        }
    }
}
```

## Validation and deployment check

Run the dependency-free checks before deployment:

```sh
python3 -m unittest discover -s tests -v
```

Deploy from a clean checkout of the intended commit. After the static files are
copied, compare the live HTML byte-for-byte with that checkout:

```sh
sh scripts/verify-live.sh https://trip.arielzhu.space/nate/
```

The command exits non-zero and prints both SHA-256 hashes when the deployed page
does not match the checkout. This is intentionally a post-deploy check rather
than a GitHub Action because the live site may be updated after a commit lands.

## Content

The places, hotels and distances are hardcoded in `nate/index.html` (the `P`,
`VISITS`, `PROPS`, `DAYS` objects) — tune those for your own trip. Phone and
booking links are per-visit too.
