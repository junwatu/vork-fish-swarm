# Fish Swarm — a GPU-simulated school of fish (Vork + Slang)

A fish swarm (bait ball) of silvery fish mills over a sunlit reef floor. The school is
**simulated by scene-owned Slang compute programs** and rendered as one
instanced draw on an NVIDIA L40S. No external assets, no Blender: the water is a
procedural environment program.

Deliverables: hero stills and a short clip.

## Requirements

This project requires the [Vork 3D engine](https://github.com/voyager-so/vork) for compute simulation and rendering. When running cloud renders on Modal (`modal/render.py`), Vork is automatically installed inside the container image.

## How it is built

`prepare.py` writes `scene/` (scene JSON, shaders, zero-filled state buffers);
`modal/render.py` bakes `scene/` into the image and renders on Modal.

```
python3 prepare.py
modal run modal/render.py --spec spec-stills.json --out-dir renders/stills
# clip: 8 chunks in parallel, then stitch
modal run modal/render.py --spec spec-clip-chunks.json --out-dir /tmp/chunks
ffmpeg -f concat -safe 0 -i list.txt -c copy renders/clip/fish-swarm.mp4
```

`spec-clip.json` renders the whole range in one pass (slow); `spec-clip-chunks.json`
splits it across parallel containers (see `reports/fish-swarm.md`).

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
