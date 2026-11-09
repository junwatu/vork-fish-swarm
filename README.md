# Fish Swarm — a GPU-simulated school of fish (Vork + Slang)

A fish swarm (bait ball) of silvery fish mills over a sunlit reef floor. The school is
**simulated by scene-owned Slang compute programs** and rendered as one
instanced draw on an **NVIDIA L40S on [Modal.com](https://modal.com)**. No
external assets, no Blender: the water is a procedural environment program.

Deliverables: hero stills and a short clip.

## Requirements

This project renders on **[Modal.com](https://modal.com)**, one **NVIDIA L40S**
(48 GB) per job, using the [Vork 3D engine](https://github.com/voyager-so/vork)
for the compute simulation and rendering. Vork is installed automatically inside
the Modal container image (`modal/render.py`), so **no local GPU is required** —
only the Modal CLI and `python3`.

## How it is built

`prepare.py` writes `scene/` (scene JSON, shaders, zero-filled state buffers);
`modal/render.py` bakes `scene/` into the image and renders on Modal. For the
render commands, see [How to render](#how-to-render) below.

## How to render

Rendering runs in the cloud on **[Modal.com](https://modal.com)**, one
**NVIDIA L40S** (48 GB) per job. Vork is baked into the container image
(`VORK_VERSION` in `modal/render.py`), so nothing but the Modal CLI, `python3`
and `ffmpeg` is needed locally.

### Prerequisites

* A [Modal.com](https://modal.com) account, logged in once with `modal token new`.
* `python3` locally (to rebuild the scene).
* `ffmpeg` locally (only to stitch the clip chunks).

### Environment (baked into the Modal image)

`modal/render.py` builds the render image on first launch, so the toolchain is
reproducible without any local setup:

| | |
| --- | --- |
| cloud / GPU | **Modal.com**, 1 × **NVIDIA L40S** (48 GB), 8 vCPU, 32 GB RAM |
| base image | `ubuntu:22.04` + Python 3.13 |
| Vork | pinned `VORK_VERSION = "0.2.0"` (`modal/render.py`) |
| render stack | Vulkan (NVIDIA driver), Slang, OIDN GPU denoiser, ffmpeg/NVENC |
| cache | shared Modal volume `vork-l40s-cache` (`/cache`) — persists shader setup |

### Reproduce everything (one command)

`run.sh` builds the scene and drives the whole cloud pipeline:

```
./run.sh stills   # scene + the three std/path stills
./run.sh draft    # scene + fast std/draft clip
./run.sh clip     # scene + 8-way chunked std/path clip, stitched
./run.sh all      # stills + clip   (default)
```

The rest of this section is exactly what `run.sh` does, step by step.

### 1. (Re)build the scene

`modal/render.py` bakes `scene/` into the image **at launch**, so if you changed
`prepare.py` or any `.slang` shader, regenerate the folder first:

```
python3 prepare.py
```

### 2. Stills

Three independent jobs, three containers in parallel:

```
modal run modal/render.py --spec spec-stills.json --out-dir renders/stills
```

Writes `renders/stills/still-03s.png`, `still-06s.png`, `still-09s.png`.

### 3. The clip

Fast preview (`std/draft`, one container):

```
modal run modal/render.py --spec spec-clip-draft.json --out-dir renders/clip
```

Final quality (`std/path`). At ≈62 s/frame on one L40S the full range is
≈3.3 GPU-hours, so `spec-clip-chunks.json` splits it into eight parallel jobs and
you stitch the result losslessly:

```
modal run modal/render.py --spec spec-clip-chunks.json --out-dir /tmp/chunks

# stitch the eight chunks (absolute paths in the concat list)
cd /tmp/chunks
for f in fish-swarm-chunk*.mp4; do echo "file '$PWD/$f'"; done > list.txt
cd -
ffmpeg -f concat -safe 0 -i /tmp/chunks/list.txt -c copy renders/clip/fish-swarm.mp4
```

`spec-clip.json` renders the whole range in a single container instead (simplest,
≈3.3 h). See `reports/fish-swarm.md` for timings and cost.

### Spec format

A spec is a JSON list of jobs; **each job runs in its own container**, so longer
work is made parallel by splitting it. A job is a single frame (`at`) or a range
(`frame_start`/`frame_end`):

```json
[
 {"out": "still-03s.png", "shot": "scene.json", "profile": "std/path",
  "resolution": "1920x1080", "at": 3.0},
 {"out": "clip.mp4", "shot": "scene.json", "profile": "std/path",
  "resolution": "1920x1080", "frame_start": 48, "frame_end": 240}
]
```

| profile | |
| --- | --- |
| `std/draft` | fast preview, coarse |
| `std/final` | balanced |
| `std/path` | top quality — the delivered look (used by the specs) |

Cost is billed per GPU-second, so splitting a clip across GPUs buys wall-clock but
not money; the 193-frame `std/path` clip (≈3.4 GPU-h) cost ≈$6.7.

### Determinism

`prepare.py` is pure math — no randomness — so a fresh run reproduces the same
`scene/` (fish mesh, reef, camera arc, sun) byte-for-byte from these constants:

| | |
| --- | --- |
| fish | 12 000 |
| grid | 64×32×64 × 4 (0.75 m cells) |
| schedule | `dt = 1/60`, seed 11 |
| roost | `(0, 9, 0)` |
| fish mesh | 14 triangles |
| reef mesh | 72×72 grid → 10 368 triangles |
| camera | orbit r ≈ 24 m, ~92° sweep, 241 keys over t = 0–20 s |
| display | `std/agx`, exposure 0.0; motion-blur shutter 0.4 |

The simulation is deterministic too — the compute programs read `seed` from
`scene.simulation`, so the same Vork version produces the same school. A
different Vork release may render slightly differently.

### Expected outputs

| | |
| --- | --- |
| stills | `still-03s.png`, `still-06s.png`, `still-09s.png` — 1920×1080 `std/path` |
| clip | `fish-swarm.mp4` — h264, 1920×1080, 24 fps, 193 frames, ≈8.0 s, ≈16 MB |
| clip time | ≈62 s/frame on one L40S → ≈28 min wall split 8 ways (≈3.4 GPU-h) |
| clip cost | ≈$6.7 on Modal.com (billed per GPU-second) |

## The simulation

`scene.simulation` runs a fixed 60 Hz schedule; each tick is four dispatches:

| program | role |
| --- | --- |
| `initialize` | seed 12 000 fish on a milling shell around the swarm (once, at t0) |
| `clear` | empty the spatial grid |
| `grid` | hash fish into a 64×32×64 grid (0.75 m cells), four representatives per cell |
| `advance` | 12-nearest-neighbour schooling + roost spring + tangential drive + drag |
| `place` | commit the step, face the heading, wag the tail, bank the turn |

The fish are drawn as **one instanced mesh**: `TRANSLATION`/`ROTATION`/`SCALE`
are the per-instance buffers the compute programs write.

## The underwater look

This release has **no participating medium**, so the water is faked honestly:

* **Water** (`water.slang`) — a custom `environment` program: a blue-green
  gradient that brightens toward the surface, a sun glow/disk, and a moving
  caustic shimmer. It lights the scene and paints the backdrop.
* **Reef floor** (`seabed.slang`) — a dune-shaped sand plain with an animated
  procedural **caustic** pattern, lit from above.
* **Colour absorption** — both materials fade toward the water colour by
  distance with a *per-channel* coefficient (red first, then green) so far
  geometry goes blue: the main underwater depth cue.
* **Fish** (`fish.slang`) — countershading, a per-fish tone, and a strong
  specular so the school flashes silver as it rolls.

The eye position for the absorption rides the camera's animation track (a
material input), so the fog is measured from the camera, not the ball.

## Deliverables

| file | |
| --- | --- |
| `renders/stills/still-03s.png` | `std/path` 1920×1080, t = 3 s |
| `renders/stills/still-06s.png` | `std/path` 1920×1080, t = 6 s |
| `renders/stills/still-09s.png` | `std/path` 1920×1080, t = 9 s |
| `renders/clip/fish-swarm.mp4` | `std/path` 1920×1080, frames 48–240 (t ≈ 2–10 s), 8.0 s @ 24 fps |
| `renders/clip/fish-swarm-draft.mp4` | `std/draft` preview of the same range (fast) |
| `renders/stills/std-final/` | earlier `std/final` stills, kept for comparison |

The `std/path` clip was rendered as 8 parallel chunks and stitched; see
`reports/fish-swarm.md` for the method, timings and cost.
