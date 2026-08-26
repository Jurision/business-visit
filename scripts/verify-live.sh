#!/usr/bin/env sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
live_url=${1:-https://trip.arielzhu.space/nate/}
live_file=$(mktemp)
trap 'rm -f "$live_file"' EXIT HUP INT TERM

curl --fail --silent --show-error --compressed "$live_url" -o "$live_file"

if cmp -s "$repo_root/nate/index.html" "$live_file"; then
    echo "OK: live HTML matches nate/index.html"
    exit 0
fi

echo "ERROR: live HTML does not match nate/index.html" >&2
sha256sum "$repo_root/nate/index.html" "$live_file" >&2
exit 1
