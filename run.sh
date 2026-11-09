#!/usr/bin/env bash
# Reproduce the fish-swarm scene and its renders on Modal.com (NVIDIA L40S).
#
#   ./run.sh stills   # rebuild scene + render the three std/path stills
#   ./run.sh draft    # rebuild scene + render the fast std/draft clip
#   ./run.sh clip     # rebuild scene + 8-way chunked std/path clip, stitched
#   ./run.sh all      # stills + clip   (default)
#
# Requires: the Modal CLI logged in (once: `modal token new`), python3, ffmpeg.
# Override the Modal binary with MODAL=/path/to/modal if it is not on PATH.
set -euo pipefail
cd "$(dirname "$0")"

MODAL="${MODAL:-modal}"
WHAT="${1:-all}"
CHUNKS="${CHUNKS:-/tmp/chunks}"

case "$WHAT" in
    stills|draft|clip|all) ;;
    *) echo "usage: $0 {stills|draft|clip|all}" >&2; exit 2 ;;
esac

echo "== rebuilding scene =="
python3 prepare.py

if [ "$WHAT" = stills ] || [ "$WHAT" = all ]; then
    echo "== stills (std/path, 3 containers) =="
    "$MODAL" run modal/render.py --spec spec-stills.json --out-dir renders/stills
fi

if [ "$WHAT" = draft ]; then
    echo "== draft clip (std/draft, 1 container) =="
    "$MODAL" run modal/render.py --spec spec-clip-draft.json --out-dir renders/clip
fi

if [ "$WHAT" = clip ] || [ "$WHAT" = all ]; then
    echo "== clip (std/path, 8 parallel chunks) =="
    rm -rf "$CHUNKS"
    mkdir -p "$CHUNKS"
    "$MODAL" run modal/render.py --spec spec-clip-chunks.json --out-dir "$CHUNKS"

    echo "== stitching chunks =="
    : > "$CHUNKS/list.txt"
    for f in "$CHUNKS"/fish-swarm-chunk*.mp4; do
        printf "file '%s'\n" "$f" >> "$CHUNKS/list.txt"
    done
    mkdir -p renders/clip
    ffmpeg -y -f concat -safe 0 -i "$CHUNKS/list.txt" -c copy renders/clip/fish-swarm.mp4
fi

echo "== done =="
