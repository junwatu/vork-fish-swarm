# Bait ball — build + render report

**Project:** `vork-baitball` (Vork + Slang, NVIDIA L40S on Modal).
**Deliverables:** 3 stills (`renders/stills/still-03s|06s|09s.png`) and a short
clip (`renders/clip/baitball.mp4`), all at the top `std/path` profile.

## What was built

A GPU-simulated school of 12 000 fish milling as a bait ball over a caustic reef
floor. The school is simulated entirely by scene-owned Slang compute programs and
drawn as a single instanced mesh; the underwater look is a custom environment
program plus per-material distance absorption. No external assets, no Blender.

## Pipeline

`prepare.py` writes `scene/` (scene JSON, shaders, zero-filled state buffers).
`modal/render.py` bakes `scene/` into the image and renders on Modal. Jobs in a
spec each run in **their own container, in parallel** (`render_batch.map`), so a
long clip can be split across many GPUs; outputs come back base64.

```
python3 prepare.py
modal run modal/render.py --spec spec-stills.json     --out-dir renders/stills
modal run modal/render.py --spec spec-clip-chunks.json --out-dir /tmp/chunks
ffmpeg -f concat -safe 0 -i list.txt -c copy renders/clip/baitball.mp4
```

## Simulation

Fixed 60 Hz schedule (`dt = 1/60`, seed 11). Each tick: `clear → grid → advance
→ place`; `initialize` runs once at t0.

| program | role |
| --- | --- |
| `initialize` | seed 12 000 fish on a milling shell (r ≈ 3.5–6.5 m) around the roost |
| `clear` | fill the spatial grid with the `0xffffffff` sentinel |
| `grid` | hash fish into a 64×32×64 grid (0.75 m cells), 4 reps/cell |
| `advance` | 12-nearest-neighbour schooling + roost spring + tangential drive + drag |
| `place` | commit the step; face heading; tail wag, nod and bank |

With low cohesion (0.30) and strong separation (14.0) the school settles at a
~5–6 m radius — the spacing (≈0.4 m) at which 1-m fish read as individuals. The
roost is fixed at `(0, 9, 0)`, so the camera (which aims at the roost) always
holds the ball centred while it swirls.

## Underwater look

This release has **no participating medium** (`docs/help/limits.md`: medium
bindings warn/ignored; `std/fog`/`std/particles` are stubs), so the water is
faked per-material:

* **Water** (`water.slang`) — a custom `environment` program: a blue-green
  gradient brightening toward the surface, a sun glow/disk, and a moving caustic
  shimmer. Environment light **and** backdrop.
* **Reef floor** (`seabed.slang`) — dune-shaped sand with an animated procedural
  caustic pattern (domain-warped), lit from above.
* **Colour absorption** — `fish` and `seabed` fade toward the water colour by
  camera distance with a *per-channel* coefficient (red first): the main
  underwater depth cue. The eye position rides the camera's animation track as a
  material input.
* **Fish** (`fish.slang`) — countershading, a per-fish tone, strong specular.

## Settings

| | |
| --- | --- |
| fish | 12 000 |
| grid | 64×32×64 × 4 (0.75 m cells) |
| roost | `(0, 9, 0)` |
| camera | 32 mm, orbit r ≈ 24 m, ~92° sweep, aim at roost |
| sun | elevation 1.05, rotation 0.5; energy 3.0 |
| water env light | energy 1.00 |
| display | `std/agx`, exposure 0.0 |
| motion blur | shutter 0.4 |

## Renders

| output | profile | res | range | time |
| --- | --- | --- | --- | --- |
| `renders/stills/still-03s.png` | `std/path` | 1920×1080 | t = 3 s | 123.4 s (cold pipeline) |
| `renders/stills/still-06s.png` | `std/path` | 1920×1080 | t = 6 s | 64.0 s |
| `renders/stills/still-09s.png` | `std/path` | 1920×1080 | t = 9 s | 62.2 s |
| `renders/clip/baitball.mp4` | `std/path` | 1920×1080 | frames 48–240 (t ≈ 2–10 s) | ~28 min wall (8-way parallel) |
| `renders/clip/baitball-draft.mp4` | `std/draft` | 1920×1080 | frames 48–240 | 29 s (single GPU) |

Exposure: mean 0.41, 0 % clipped, <0.1 % near-black on every output.
Clip: h264, 1920×1080, 24 fps, **193 frames, 8.04 s, 16.3 MB**.

### Parallel clip render

`std/path` costs ≈ 62 s/frame on one L40S, so the 193-frame clip is ~3.3
GPU-hours. Split into **8 chunks and run in 8 containers at once**:

| | |
| --- | --- |
| chunks | frames 48–72, 73–96, …, 217–240 (25/24×7) |
| per chunk | 1497–1708 s ≈ 25–28 min |
| wall time | ≈ 28 min (vs ~3.3 h sequential) |
| GPU time | ≈ 12 400 GPU-s ≈ 3.4 GPU-h × $1.951 ≈ **$6.7** |

Cost is the same however many GPUs are used (Modal bills per GPU-second); more
GPUs buy wall-clock only. The chunks are stitched with `ffmpeg -f concat -c
copy`; the frame-72/73 seam is continuous.

## Render logs (recorded)

Full Vork/Modal output for the final renders is kept verbatim:

* `reports/render-stills-path.log` — the three `std/path` stills.
* `reports/render-clip-path.log` — the 8-way parallel `std/path` clip.

Each log contains the Modal app URL, `vork setup`, per-job `vork render` lines
with frame counts and exposure, and the `WROTE`/`REPORT` lines.

## Notes / what the iteration taught

* **Grid scale matters.** The first cut used 2 m cells over a 2 m ball — the
  neighbour search was pure noise and the school collapsed then fragmented.
  Matching cell size (0.75 m) to the ball (≈5 m) fixed it.
* **Fish count ↔ ball size.** 120 k one-metre fish packed tightly is physically a
  ~15 m ball; at close range that is mush. 12 k fish in a ~5 m ball gives the
  density where individual fish read.
* **The predator was cut.** A barracuda passing *through* the ball scattered it
  violently and shoved the whole school (period ≈ 10 s), so it never held a
  frame. The milling motion alone carries the shot.
* **A fixed roost** keeps the school under the camera; a moving roost made the
  ball drift across frame faster than the camera could follow.
* **`std/path` vs `std/final` here** is a modest step: path resolves the
  school's interior self-shadowing (a darker occluded core). The seabed caustics
  are procedural, so they are identical between profiles.
